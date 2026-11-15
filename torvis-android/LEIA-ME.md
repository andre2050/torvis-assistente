# TORVIS 2026 — Android

O app do celular é uma casca Java (WebView + voz nativa do Android) em volta de
uma única página: `TORVIS-2026-Android.html`. A mesma página abre no Chrome do
celular, só que sem voz, lanterna nem volume.

## O que tem aqui

```
torvis-android/
├── TORVIS-2026-Android.html   interface completa (uma página, sem servidor)
├── LEIA-ME.md
└── apk/
    ├── AndroidManifest.xml    permissões, activity, receptor de alarme
    ├── compilar.sh            build sem Android Studio
    ├── torvis.keystore        chave de assinatura (senha torvis2026)
    ├── res/                   ícones e textos
    └── src/com/andreluiz/torvis/
        ├── MainActivity.java  ponte Java: voz, volume, lanterna, lembretes,
        │                      brilho, despertador, música, telefone, agenda,
        │                      localização, apps, atualização
        └── Alarme.java        publica a notificação do lembrete
```

## Recompilar

```bash
export ANDROID_HOME=/caminho/do/Android/sdk
cd torvis-android/apk && ./compilar.sh
```

Precisa de JDK 17 e do SDK com `platforms/android-34` e `build-tools/34.0.0`.
O resultado é `TORVIS-2026.apk`, já assinado.

**A chave é sempre a mesma.** `torvis.keystore` guarda a identidade do app; se
mudar, o Android recusa instalar por cima e o usuário perde os dados.

## Atualizar de dentro do app

O botão **Atualizar** consulta a última release do repositório e, se houver
versão nova, abre o download do APK. O Android pede confirmação antes de
instalar; não existe instalação silenciosa fora da Play Store.

## Versão

A versão aparece em dois lugares: `versionName` no `AndroidManifest.xml` e na
constante devolvida por `Ponte.versao()`. Elas precisam combinar com a tag da
release, senão o botão de atualização fica dizendo que já está atualizado.
