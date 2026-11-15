package com.andreluiz.torvis;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;
import android.os.Build;

/**
 * Quem toca o lembrete. O AlarmManager acorda este receptor na hora marcada e
 * ele publica a notificação — sem servidor, sem internet e funcionando com o
 * app fechado.
 */
public class Alarme extends BroadcastReceiver {

    @Override
    public void onReceive(Context contexto, Intent intencao) {
        String titulo = intencao.getStringExtra("titulo");
        String texto = intencao.getStringExtra("texto");
        int id = intencao.getIntExtra("id", 1);

        NotificationManager gestor =
            (NotificationManager) contexto.getSystemService(Context.NOTIFICATION_SERVICE);

        if (Build.VERSION.SDK_INT >= 26) {
            NotificationChannel canal = new NotificationChannel("torvis.lembretes",
                    "Lembretes do TORVIS", NotificationManager.IMPORTANCE_HIGH);
            gestor.createNotificationChannel(canal);
        }

        Intent abrir = new Intent(contexto, MainActivity.class);
        int bandeira = PendingIntent.FLAG_UPDATE_CURRENT;
        if (Build.VERSION.SDK_INT >= 23) bandeira |= PendingIntent.FLAG_IMMUTABLE;
        PendingIntent toque = PendingIntent.getActivity(contexto, id, abrir, bandeira);

        Notification.Builder construtor = Build.VERSION.SDK_INT >= 26
                ? new Notification.Builder(contexto, "torvis.lembretes")
                : new Notification.Builder(contexto);

        construtor.setContentTitle(titulo == null ? "TORVIS" : titulo)
                 .setContentText(texto == null ? "" : texto)
                 .setSmallIcon(android.R.drawable.ic_popup_reminder)
                 .setAutoCancel(true)
                 .setContentIntent(toque)
                 .setDefaults(Notification.DEFAULT_ALL)
                 .setStyle(new Notification.BigTextStyle().bigText(texto == null ? "" : texto));

        gestor.notify(id, construtor.build());
    }
}
