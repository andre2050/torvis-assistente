package com.andreluiz.torvis;

import android.Manifest;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.os.Build;
import android.os.Bundle;
import android.speech.RecognizerIntent;
import android.speech.RecognitionListener;
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
 * A interface é a mesma do arquivo mobile (assets/index.html); esta classe só
 * entrega o que o WebView não tem: ouvir pelo microfone do aparelho e falar.
 * O Web Speech API do Chrome não existe dentro de um WebView, então a voz
 * passa por aqui em vez de depender do navegador.
 */
public class MainActivity extends Activity {

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

    private static final int PEDIDO_MIC = 71;
    private static final int PEDIDO_FALA = 72;

    private WebView tela;
    private TextToSpeech voz;
    private SpeechRecognizer escuta;
    private boolean vozPronta = false;
    private boolean ouvindo = false;

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

    /* ── ponte com a interface ───────────────────────────────────────────── */

    class Ponte {

        @JavascriptInterface
        public String plataforma() {
            return "android";
        }

        @JavascriptInterface
        public String versao() {
            return "6.6.3";
        }

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
                public void run() {
                    if (vozPronta) voz.stop();
                }
            });
        }

        @JavascriptInterface
        public void ouvir() {
            runOnUiThread(new Runnable() {
                public void run() {
                    iniciarEscuta();
                }
            });
        }
    }

    /* ── microfone ───────────────────────────────────────────────────────── */

    private boolean temPermissaoMic() {
        if (Build.VERSION.SDK_INT < 23) return true;
        return checkSelfPermission(Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED;
    }

    private void iniciarEscuta() {
        if (ouvindo) return;
        if (!temPermissaoMic()) {
            if (Build.VERSION.SDK_INT >= 23) {
                requestPermissions(new String[]{Manifest.permission.RECORD_AUDIO}, PEDIDO_MIC);
            }
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
                @Override public void onError(int erro) { ouvindo = false; }
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
        if (codigo == PEDIDO_MIC) {
            if (resultados.length > 0 && resultados[0] == PackageManager.PERMISSION_GRANTED) {
                iniciarEscuta();
            } else {
                avisarJs("O microfone foi negado. Libere em Configurações do Android > Apps > TORVIS.");
            }
        }
    }

    private void avisarJs(String mensagem) {
        if (tela == null) return;
        tela.evaluateJavascript("window.torvisAviso && window.torvisAviso("
            + aspas(mensagem) + ")", null);
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
        if (tela != null) tela.destroy();
        super.onDestroy();
    }
}
