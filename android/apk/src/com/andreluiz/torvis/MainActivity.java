package com.andreluiz.torvis;

import android.Manifest;
import android.app.Activity;
import android.app.AlarmManager;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraManager;
import android.media.AudioManager;
import android.net.ConnectivityManager;
import android.net.NetworkInfo;
import android.net.Uri;
import android.os.BatteryManager;
import android.os.Build;
import android.os.Bundle;
import android.os.VibrationEffect;
import android.os.Vibrator;
import android.speech.RecognitionListener;
import android.speech.RecognizerIntent;
import android.speech.SpeechRecognizer;
import android.speech.tts.TextToSpeech;
import android.webkit.JavascriptInterface;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import java.util.ArrayList;
import java.util.Locale;

/**
 * Casca Android do TORVIS 2026.
 *
 * A interface é a mesma do arquivo mobile (assets/index.html). Esta classe entrega
 * o que um WebView não tem: voz do aparelho, volume, lanterna, lembretes com
 * notificação, abertura de apps e leitura do estado do sistema.
 *
 * Regra de ouro: nada aqui pode derrubar o app. Toda chamada devolve texto
 * (nunca lança para o JavaScript) para que a tela mostre o motivo.
 */
public class MainActivity extends Activity {

    private static final int PEDIDO_MIC = 71;
    private static final int PEDIDO_CAMERA = 73;
    private static final int PEDIDO_NOTIF = 74;
    private static final String CANAL = "torvis.lembretes";

    private WebView tela;
    private TextToSpeech voz;
    private SpeechRecognizer escuta;
    private boolean vozPronta = false;
    private boolean ouvindo = false;
    private boolean querLanterna = false;
    private boolean lanternaAcesa = false;

    /** Escapa texto para virar literal de JavaScript com segurança. */
    private static String aspas(String s) {
        if (s == null) return "\"\"";
        StringBuilder b = new StringBuilder("\"");
        for (char c : s.toCharArray()) {
            switch (c) {
                case '"': b.append("\\\""); break;
                case '\\': b.append("\\\\"); break;
                case '\n': b.append("\\n"); break;
                case '\r': b.append("\\r"); break;
                case '\t': b.append("\\t"); break;
                default:
                    if (c < 0x20) b.append(String.format("\\u%04x", (int) c));
                    else b.append(c);
            }
        }
        return b.append("\"").toString();
    }

    @Override
    protected void onCreate(Bundle estado) {
        super.onCreate(estado);

        tela = new WebView(this);
        WebSettings c = tela.getSettings();
        c.setJavaScriptEnabled(true);
        c.setDomStorageEnabled(true);
        c.setMediaPlaybackRequiresUserGesture(false);
        c.setAllowFileAccess(true);
        c.setTextZoom(100);
        tela.setBackgroundColor(0xFF0A0D12);
        tela.setWebViewClient(new WebViewClient());
        tela.addJavascriptInterface(new Ponte(), "AndroidPonte");
        tela.loadUrl("file:///android_asset/index.html");
        setContentView(tela);

        criarCanal();

        voz = new TextToSpeech(this, new TextToSpeech.OnInitListener() {
            @Override
            public void onInit(int statuso) {
                if (statuso != TextToSpeech.SUCCESS) return;
                int r = voz.setLanguage(new Locale("pt", "BR"));
                if (r == TextToSpeech.LANG_MISSING_DATA || r == TextToSpeech.LANG_NOT_SUPPORTED) {
                    voz.setLanguage(Locale.getDefault());
                }
                vozPronta = true;
            }
        });
    }

    private void criarCanal() {
        if (Build.VERSION.SDK_INT < 26) return;
        NotificationManager gestor = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        NotificationChannel canal = new NotificationChannel(CANAL, "Lembretes do TORVIS",
                NotificationManager.IMPORTANCE_HIGH);
        canal.setDescription("Avisos que você pediu ao assistente");
        gestor.createNotificationChannel(canal);
    }

    /* ── ponte com a interface ───────────────────────────────────────────── */

    class Ponte {

        @JavascriptInterface
        public String plataforma() { return "android"; }

        @JavascriptInterface
        public String versao() { return "6.6.4"; }

        /* voz */
        @JavascriptInterface
        public void falar(final String texto) {
            runOnUiThread(new Runnable() {
                public void run() {
                    if (!vozPronta || texto == null) return;
                    voz.speak(texto, TextToSpeech.QUEUE_FLUSH, null, "torvis");
                }
            });
        }

        @JavascriptInterface
        public void pararFala() {
            runOnUiThread(new Runnable() {
                public void run() { if (vozPronta) voz.stop(); }
            });
        }

        @JavascriptInterface
        public void ouvir() {
            runOnUiThread(new Runnable() {
                public void run() { iniciarEscuta(); }
            });
        }

        /* volume do aparelho, em porcentagem */
        @JavascriptInterface
        public int volume() {
            try {
                AudioManager som = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
                int maximo = som.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
                int atual = som.getStreamVolume(AudioManager.STREAM_MUSIC);
                return maximo == 0 ? 0 : Math.round(atual * 100f / maximo);
            } catch (Exception e) { return -1; }
        }

        @JavascriptInterface
        public boolean definirVolume(int porcentagem) {
            try {
                AudioManager som = (AudioManager) getSystemService(Context.AUDIO_SERVICE);
                int maximo = som.getStreamMaxVolume(AudioManager.STREAM_MUSIC);
                int alvo = Math.max(0, Math.min(100, porcentagem));
                som.setStreamVolume(AudioManager.STREAM_MUSIC, Math.round(maximo * alvo / 100f), 0);
                return true;
            } catch (Exception e) { return false; }
        }

        /* lanterna, usando a câmera traseira */
        @JavascriptInterface
        public boolean lanterna(boolean ligar) {
            querLanterna = ligar;
            if (Build.VERSION.SDK_INT < 23) return false;
            if (!temPermissao(Manifest.permission.CAMERA)) {
                pedirPermissao(new String[]{Manifest.permission.CAMERA}, PEDIDO_CAMERA);
                return false;
            }
            return aplicarLanterna(ligar);
        }

        @JavascriptInterface
        public boolean lanternaAcesa() { return lanternaAcesa; }

        /* lembrete com notificação, em minutos a partir de agora */
        @JavascriptInterface
        public String lembrar(String titulo, String texto, int minutos) {
            if (Build.VERSION.SDK_INT >= 33 && !temPermissao("android.permission.POST_NOTIFICATIONS")) {
                pedirPermissao(new String[]{"android.permission.POST_NOTIFICATIONS"}, PEDIDO_NOTIF);
            }
            try {
                int id = (int) (System.currentTimeMillis() % 100000);
                Intent aviso = new Intent(MainActivity.this, Alarme.class);
                aviso.putExtra("titulo", titulo == null ? "TORVIS" : titulo);
                aviso.putExtra("texto", texto == null ? "" : texto);
                aviso.putExtra("id", id);

                int bandeira = PendingIntent.FLAG_UPDATE_CURRENT;
                if (Build.VERSION.SDK_INT >= 23) bandeira |= PendingIntent.FLAG_IMMUTABLE;
                PendingIntent pendente = PendingIntent.getBroadcast(MainActivity.this, id, aviso, bandeira);

                long quando = System.currentTimeMillis() + Math.max(1, minutos) * 60000L;
                AlarmManager alarme = (AlarmManager) getSystemService(Context.ALARM_SERVICE);
                if (Build.VERSION.SDK_INT >= 23) {
                    try {
                        alarme.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, quando, pendente);
                    } catch (SecurityException semPermissao) {
                        alarme.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, quando, pendente);
                    }
                } else {
                    alarme.set(AlarmManager.RTC_WAKEUP, quando, pendente);
                }
                return "ok";
            } catch (Exception e) {
                return "não consegui agendar: " + e.getMessage();
            }
        }

        /* abrir site, app ou busca */
        @JavascriptInterface
        public String abrir(String alvo) {
            try {
                if (alvo == null || alvo.trim().isEmpty()) return "nada para abrir";
                String limpo = alvo.trim();
                Intent intencao;
                if (limpo.startsWith("http://") || limpo.startsWith("https://")
                        || limpo.startsWith("whatsapp:") || limpo.startsWith("mailto:")
                        || limpo.startsWith("tel:") || limpo.startsWith("sms:")
                        || limpo.startsWith("intent:")) {
                    intencao = new Intent(Intent.ACTION_VIEW, Uri.parse(limpo));
                } else if (limpo.matches("[a-z0-9_.]+\\.[a-z0-9_.]+")) {
                    intencao = getPackageManager().getLaunchIntentForPackage(limpo);
                    if (intencao == null) return "app não instalado: " + limpo;
                } else {
                    intencao = new Intent(Intent.ACTION_VIEW,
                            Uri.parse("https://www.google.com/search?q=" + Uri.encode(limpo)));
                }
                intencao.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intencao);
                return "ok";
            } catch (Exception e) {
                return "não abriu: " + e.getMessage();
            }
        }

        @JavascriptInterface
        public String youtube(String termo) {
            try {
                String busca = termo == null ? "" : termo.trim();
                Intent intencao = new Intent(Intent.ACTION_VIEW,
                        Uri.parse("https://www.youtube.com/results?search_query=" + Uri.encode(busca)));
                intencao.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(intencao);
                return "ok";
            } catch (Exception e) { return "não abriu: " + e.getMessage(); }
        }

        /* estado do aparelho */
        @JavascriptInterface
        public int bateria() {
            try {
                BatteryManager bm = (BatteryManager) getSystemService(Context.BATTERY_SERVICE);
                return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY);
            } catch (Exception e) { return -1; }
        }

        @JavascriptInterface
        public boolean carregando() {
            try {
                Intent estado = registerReceiver(null, new android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED));
                if (estado == null) return false;
                int situacao = estado.getIntExtra(BatteryManager.EXTRA_STATUS, -1);
                return situacao == BatteryManager.BATTERY_STATUS_CHARGING
                        || situacao == BatteryManager.BATTERY_STATUS_FULL;
            } catch (Exception e) { return false; }
        }

        @JavascriptInterface
        public String rede() {
            try {
                ConnectivityManager cm = (ConnectivityManager) getSystemService(Context.CONNECTIVITY_SERVICE);
                NetworkInfo info = cm.getActiveNetworkInfo();
                if (info == null || !info.isConnected()) return "sem rede";
                return info.getType() == ConnectivityManager.TYPE_WIFI ? "wi-fi" : "dados";
            } catch (Exception e) { return "?"; }
        }

        /* utilidades do sistema */
        @JavascriptInterface
        public void vibrar(int milissegundos) {
            try {
                Vibrator v = (Vibrator) getSystemService(Context.VIBRATOR_SERVICE);
                if (v == null) return;
                if (Build.VERSION.SDK_INT >= 26) {
                    v.vibrate(VibrationEffect.createOneShot(Math.max(20, milissegundos),
                            VibrationEffect.DEFAULT_AMPLITUDE));
                } else {
                    v.vibrate(Math.max(20, milissegundos));
                }
            } catch (Exception e) { }
        }

        @JavascriptInterface
        public void copiar(String texto) {
            try {
                ClipboardManager area = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                area.setPrimaryClip(ClipData.newPlainText("TORVIS", texto == null ? "" : texto));
            } catch (Exception e) { }
        }

        @JavascriptInterface
        public void compartilhar(String texto) {
            try {
                Intent enviar = new Intent(Intent.ACTION_SEND);
                enviar.setType("text/plain");
                enviar.putExtra(Intent.EXTRA_TEXT, texto == null ? "" : texto);
                Intent escolha = Intent.createChooser(enviar, "Compartilhar pelo TORVIS");
                escolha.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
                startActivity(escolha);
            } catch (Exception e) { }
        }
    }

    /* ── microfone ───────────────────────────────────────────────────────── */

    private boolean temPermissao(String permissao) {
        if (Build.VERSION.SDK_INT < 23) return true;
        return checkSelfPermission(permissao) == PackageManager.PERMISSION_GRANTED;
    }

    private void pedirPermissao(String[] permissoes, int codigo) {
        if (Build.VERSION.SDK_INT >= 23) requestPermissions(permissoes, codigo);
    }

    private boolean aplicarLanterna(boolean ligar) {
        try {
            CameraManager cameras = (CameraManager) getSystemService(Context.CAMERA_SERVICE);
            String traseira = null;
            for (String id : cameras.getCameraIdList()) {
                Boolean flash = cameras.getCameraCharacteristics(id)
                        .get(CameraCharacteristics.FLASH_INFO_AVAILABLE);
                Integer lente = cameras.getCameraCharacteristics(id)
                        .get(CameraCharacteristics.LENS_FACING);
                if (Boolean.TRUE.equals(flash)
                        && (lente == null || lente == CameraCharacteristics.LENS_FACING_BACK)) {
                    traseira = id;
                    break;
                }
            }
            if (traseira == null) {
                avisarJs("Este aparelho não tem lanterna acessível.");
                return false;
            }
            cameras.setTorchMode(traseira, ligar);
            lanternaAcesa = ligar;
            return true;
        } catch (Exception e) {
            avisarJs("Lanterna indisponível: " + e.getMessage());
            return false;
        }
    }

    private void iniciarEscuta() {
        if (ouvindo) return;
        if (!temPermissao(Manifest.permission.RECORD_AUDIO)) {
            pedirPermissao(new String[]{Manifest.permission.RECORD_AUDIO}, PEDIDO_MIC);
            return;
        }
        if (!SpeechRecognizer.isRecognitionAvailable(this)) {
            avisarJs("Este aparelho não tem reconhecimento de voz do Google instalado.");
            return;
        }

        if (escuta == null) {
            escuta = SpeechRecognizer.createSpeechRecognizer(this);
            escuta.setRecognitionListener(new RecognitionListener() {
                @Override public void onReadyForSpeech(Bundle b) { ouvindo = true; }
                @Override public void onBeginningOfSpeech() { }
                @Override public void onRmsChanged(float v) { }
                @Override public void onBufferReceived(byte[] b) { }
                @Override public void onEndOfSpeech() { ouvindo = false; }
                @Override public void onError(int erro) {
                    ouvindo = false;
                    if (erro == SpeechRecognizer.ERROR_NO_MATCH
                            || erro == SpeechRecognizer.ERROR_SPEECH_TIMEOUT) return;
                    avisarJs("Não entendi. Toque no microfone e fale de novo.");
                }
                @Override public void onResults(Bundle resultados) {
                    ouvindo = false;
                    ArrayList<String> textos =
                        resultados.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION);
                    if (textos == null || textos.isEmpty()) return;
                    String texto = textos.get(0);
                    if (texto != null && texto.trim().length() > 0) {
                        tela.evaluateJavascript("window.torvisTexto && window.torvisTexto("
                            + aspas(texto.trim()) + ")", null);
                    }
                }
                @Override public void onPartialResults(Bundle parciais) { }
                @Override public void onEvent(int tipo, Bundle b) { }
            });
        }

        Intent pedido = new Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH);
        pedido.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                        RecognizerIntent.LANGUAGE_MODEL_FREE_FORM);
        pedido.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "pt-BR");
        pedido.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 1);
        try {
            escuta.startListening(pedido);
            ouvindo = true;
        } catch (Exception e) {
            ouvindo = false;
            avisarJs("Não consegui abrir o microfone: " + e.getMessage());
        }
    }

    @Override
    public void onRequestPermissionsResult(int codigo, String[] permissoes, int[] resultados) {
        boolean liberou = resultados.length > 0
                && resultados[0] == PackageManager.PERMISSION_GRANTED;
        if (codigo == PEDIDO_MIC) {
            if (liberou) iniciarEscuta();
            else avisarJs("O microfone foi negado. Libere em Configurações > Apps > TORVIS.");
        } else if (codigo == PEDIDO_CAMERA) {
            if (liberou) aplicarLanterna(querLanterna);
            else avisarJs("Sem permissão de câmera não consigo acender a lanterna.");
        } else if (codigo == PEDIDO_NOTIF) {
            if (!liberou) avisarJs("Sem permissão de notificação o lembrete não aparece na tela.");
        }
    }

    private void avisarJs(String mensagem) {
        if (tela == null) return;
        tela.evaluateJavascript("window.torvisAviso && window.torvisAviso(" + aspas(mensagem) + ")", null);
    }

    /* ── ciclo de vida ───────────────────────────────────────────────────── */

    @Override
    public void onBackPressed() {
        moveTaskToBack(true);
    }

    @Override
    protected void onDestroy() {
        if (escuta != null) { escuta.destroy(); escuta = null; }
        if (voz != null) { voz.stop(); voz.shutdown(); }
        if (lanternaAcesa) aplicarLanterna(false);
        if (tela != null) tela.destroy();
        super.onDestroy();
    }
}
