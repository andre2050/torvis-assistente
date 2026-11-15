# APK do TORVIS 2026

O APK é uma casca nativa (WebView + voz do Android) em volta do
`android/TORVIS-2026-Android.html`. Não precisa de Android Studio nem de Gradle:
`compilar.sh` usa aapt2, javac, d8 e apksigner direto.

## Por que existe uma casca Java

O WebView do Android não implementa o Web Speech API. Dentro do APK a voz passa
por código nativo:

- `Ponte.falar(texto)` → `TextToSpeech` em pt-BR;
- `Ponte.ouvir()` → `SpeechRecognizer` com permissão de microfone pedida na hora;
- o resultado volta para a página por `window.torvisTexto(texto)`.

## Recompilar

```bash
export ANDROID_HOME=/caminho/do/Android/sdk
./compilar.sh
```

A chave de assinatura (`torvis.keystore`) precisa ser a mesma em todas as
versões, senão o Android recusa a atualização por cima.
