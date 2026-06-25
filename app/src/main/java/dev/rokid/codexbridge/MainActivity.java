package dev.rokid.codexbridge;

import android.app.Activity;
import android.graphics.Color;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.PowerManager;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.Window;
import android.view.WindowManager;
import android.widget.LinearLayout;
import android.widget.ScrollView;
import android.widget.TextView;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;

public final class MainActivity extends Activity {
    private final Handler handler = new Handler(Looper.getMainLooper());
    private TextView bodyView;
    private String lastMessage = "";
    private PowerManager.WakeLock wakeLock;
    private static final String MESSAGE_FILE = "latest.txt";
    private final Runnable tick = new Runnable() {
        @Override
        public void run() {
            refreshMessage();
            handler.postDelayed(this, 1000);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        keepDisplayVisible();
        setContentView(buildView());
        refreshMessage();
    }

    @Override
    protected void onResume() {
        super.onResume();
        acquireWakeLock();
        handler.post(tick);
    }

    @Override
    protected void onPause() {
        handler.removeCallbacks(tick);
        releaseWakeLock();
        super.onPause();
    }

    @Override
    protected void onDestroy() {
        releaseWakeLock();
        super.onDestroy();
    }

    private void keepDisplayVisible() {
        Window window = getWindow();
        window.addFlags(
                WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON
                        | WindowManager.LayoutParams.FLAG_TURN_SCREEN_ON
                        | WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED
        );
        WindowManager.LayoutParams attrs = window.getAttributes();
        attrs.screenBrightness = 1.0f;
        window.setAttributes(attrs);
        window.getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
        );
    }

    private void acquireWakeLock() {
        if (wakeLock == null) {
            PowerManager powerManager = (PowerManager) getSystemService(POWER_SERVICE);
            wakeLock = powerManager.newWakeLock(
                    PowerManager.SCREEN_DIM_WAKE_LOCK | PowerManager.ACQUIRE_CAUSES_WAKEUP,
                    "CodexBridge:DisplayWakeLock"
            );
        }
        if (!wakeLock.isHeld()) {
            wakeLock.acquire();
        }
    }

    private void releaseWakeLock() {
        if (wakeLock != null && wakeLock.isHeld()) {
            wakeLock.release();
        }
    }

    private ScrollView buildView() {
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER_HORIZONTAL);
        root.setPadding(40, 112, 40, 0);
        root.setBackgroundColor(Color.BLACK);

        bodyView = new TextView(this);
        bodyView.setTextColor(Color.rgb(190, 255, 205));
        bodyView.setTextSize(18);
        bodyView.setLineSpacing(2, 0.96f);
        bodyView.setGravity(Gravity.CENTER);
        bodyView.setIncludeFontPadding(false);
        LinearLayout.LayoutParams bodyParams = new LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT,
                ViewGroup.LayoutParams.WRAP_CONTENT
        );
        root.addView(bodyView, bodyParams);

        ScrollView scrollView = new ScrollView(this);
        scrollView.setFillViewport(true);
        scrollView.addView(root);
        return scrollView;
    }

    private void refreshMessage() {
        String message;
        java.io.File messageFile = new java.io.File(getFilesDir(), MESSAGE_FILE);
        if (!messageFile.exists()) {
            message = "Waiting for Codex...\n\nMacから tools/rokid_codex_bridge.py でテキストを送ってください。";
        } else {
            try {
                message = new String(Files.readAllBytes(messageFile.toPath()), StandardCharsets.UTF_8).trim();
            } catch (IOException e) {
                message = "Read error: " + e.getMessage();
            }
        }

        if (message.isEmpty()) {
            message = "Waiting for Codex...";
        }
        if (!message.equals(lastMessage)) {
            lastMessage = message;
            bodyView.setText(message);
        }
    }
}
