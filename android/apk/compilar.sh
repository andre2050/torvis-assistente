#!/usr/bin/env bash
# Gera o APK sem Android Studio: aapt2 + javac + d8 + apksigner.
# Requisitos: JDK 17, Android SDK com platforms/android-34 e build-tools/34.0.0.
set -euo pipefail
BT="${ANDROID_HOME:?defina ANDROID_HOME}/build-tools/34.0.0"
AJ="${ANDROID_HOME}/platforms/android-34/android.jar"
cd "$(dirname "$0")"
rm -rf build && mkdir -p build/gen build/classes build/assets
cp ../../TORVIS-2026-Android.html build/assets/index.html
"$BT/aapt2" compile --dir res -o build/res.zip
"$BT/aapt2" link -o build/base.apk -I "$AJ" --manifest AndroidManifest.xml \
  -A build/assets --java build/gen --min-sdk-version 23 --target-sdk-version 34 build/res.zip
javac -source 8 -target 8 -bootclasspath "$AJ" -classpath "$AJ" -d build/classes \
  src/com/andreluiz/torvis/*.java build/gen/com/andreluiz/torvis/R.java
"$BT/d8" --release --lib "$AJ" --min-api 23 --output build $(find build/classes -name '*.class')
cp build/base.apk build/com-dex.apk
python3 - << 'PY'
import zipfile
with zipfile.ZipFile("build/com-dex.apk", "a", zipfile.ZIP_DEFLATED) as z:
    z.write("build/classes.dex", "classes.dex")
PY
"$BT/zipalign" -f -p 4 build/com-dex.apk build/alinhado.apk
"$BT/apksigner" sign --ks torvis.keystore --ks-pass pass:torvis2026 \
  --key-pass pass:torvis2026 --out TORVIS-2026.apk build/alinhado.apk
echo "pronto: TORVIS-2026.apk"
