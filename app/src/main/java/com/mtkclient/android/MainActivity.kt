package com.mtkclient.android

import android.annotation.SuppressLint
import android.app.AlertDialog
import android.graphics.Color
import android.os.Bundle
import android.view.ViewGroup
import android.webkit.JavascriptInterface
import android.webkit.WebResourceRequest
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import android.widget.LinearLayout
import android.widget.ProgressBar
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.chaquo.python.Python
import com.chaquo.python.android.AndroidPlatform
import java.util.concurrent.Executors

class MainActivity : AppCompatActivity() {

    private lateinit var webView: WebView
    private lateinit var status: TextView
    private lateinit var progress: ProgressBar
    private lateinit var modal: FrameLayout

    private val pythonExecutor = Executors.newSingleThreadExecutor { r ->
        Thread(r, "mtkclient-python").apply { isDaemon = true }
    }
    @Volatile private var pythonReady = false
    private var dialogOk: (() -> Unit)? = null
    private var dialogCancel: (() -> Unit)? = null

    @SuppressLint("SetJavaScriptEnabled")
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        AndroidBridge.init(applicationContext, this)

        val root = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            layoutParams = ViewGroup.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT)
            setBackgroundColor(Color.rgb(0x12, 0x16, 0x1c))
        }

        status = TextView(this).apply {
            text = "Starting mtkclient Python runtime…"
            setTextColor(Color.rgb(0x9f, 0xc2, 0xea))
            setPadding(24, 16, 24, 8)
            textSize = 12f
        }
        progress = ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal).apply {
            isIndeterminate = true
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.WRAP_CONTENT)
        }

        webView = WebView(this).apply {
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.cacheMode = WebSettings.LOAD_NO_CACHE
            settings.setSupportZoom(false)
            settings.builtInZoomControls = false
            settings.useWideViewPort = true
            settings.loadWithOverviewMode = true
            setBackgroundColor(Color.rgb(0x12, 0x16, 0x1c))
            addJavascriptInterface(JsBridge(), "Android")
            webViewClient = object : WebViewClient() {
                override fun shouldOverrideUrlLoading(view: WebView?, request: WebResourceRequest?): Boolean {
                    val url = request?.url?.toString() ?: return true
                    AndroidBridge.openUrl(url)
                    return true
                }
            }
        }

        modal = FrameLayout(this).apply {
            visibility = android.view.View.GONE
            layoutParams = LinearLayout.LayoutParams(
                ViewGroup.LayoutParams.MATCH_PARENT, 0, 1f)
            setBackgroundColor(Color.parseColor("#E012161C"))
        }

        root.addView(status)
        root.addView(progress)
        root.addView(webView)
        root.addView(modal)
        setContentView(root)

        startPython()
    }

    private fun startPython() {
        pythonExecutor.execute {
            try {
                if (!Python.isStarted()) {
                    Python.start(AndroidPlatform(this))
                }
                val module = Python.getInstance().getModule("android_bridge")
                val root = module.callAttr("hasRoot").toString()
                val html = module.callAttr("bootstrap").toString()
                runOnUiThread {
                    progress.visibility = android.view.View.GONE
                    status.text = "MTKClient ready • root: $root • USB: attach your device"
                    webView.loadDataWithBaseURL("file:///android_asset/", html, "text/html", "UTF-8", null)
                    pythonReady = true
                }
            } catch (e: Throwable) {
                val msg = e.message ?: e.toString()
                runOnUiThread {
                    progress.visibility = android.view.View.GONE
                    status.text = "Startup error: $msg"
                    webView.loadDataWithBaseURL(null,
                        "<html><body style='background:#12161c;color:#ff8a80;font:14px monospace;padding:16px'>" +
                            "<h3>MTKClient failed to start</h3><pre>${htmlEscape(msg)}</pre></body></html>",
                        "text/html", "UTF-8", null)
                }
            }
        }
    }

    private fun htmlEscape(s: String) = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    inner class JsBridge {
        @JavascriptInterface
        fun handleWidget(widgetId: String, action: String, value: String) {
            pythonExecutor.execute {
                try {
                    Python.getInstance().getModule("android_bridge")
                        .callAttr("handle_widget", widgetId, action, value)
                } catch (e: Throwable) {
                    runOnUiThread { status.text = "Action error: ${e.message}" }
                }
            }
        }

        @JavascriptInterface
        fun sync(callback: String) {
            pythonExecutor.execute {
                try {
                    val json = Python.getInstance().getModule("android_bridge")
                        .callAttr("sync_state").toString()
                    runOnUiThread {
                        webView.evaluateJavascript("($callback)($json)", null)
                    }
                } catch (e: Throwable) {
                    // Polling is best-effort; never disturb the user for sync failures.
                }
            }
        }

        @JavascriptInterface
        fun refresh() {
            pythonExecutor.execute {
                try {
                    val html = Python.getInstance().getModule("android_bridge")
                        .callAttr("render_html").toString()
                    runOnUiThread {
                        webView.loadDataWithBaseURL("file:///android_asset/", html, "text/html", "UTF-8", null)
                    }
                } catch (e: Throwable) { }
            }
        }
    }

    fun showModal(html: String) {
        webView.loadDataWithBaseURL("file:///android_asset/", html, "text/html", "UTF-8", null)
        modal.visibility = android.view.View.VISIBLE
    }

    fun hideModal() {
        modal.visibility = android.view.View.GONE
        pythonExecutor.execute {
            try {
                val html = Python.getInstance().getModule("android_bridge")
                    .callAttr("render_html").toString()
                runOnUiThread {
                    webView.loadDataWithBaseURL("file:///android_asset/", html, "text/html", "UTF-8", null)
                }
            } catch (e: Throwable) { }
        }
    }

    fun setDialogCallback(cb: () -> Unit) { dialogOk = cb }
    fun setDialogCancelCallback(cb: () -> Unit) { dialogCancel = cb }
    fun resolveDialog(accepted: Boolean) {
        if (accepted) dialogOk?.invoke() else dialogCancel?.invoke()
        dialogOk = null
        dialogCancel = null
    }

    override fun onActivityResult(requestCode: Int, resultCode: Int, data: android.content.Intent?) {
        super.onActivityResult(requestCode, resultCode, data)
        AndroidBridge.onActivityResult(requestCode, resultCode, data)
    }

    override fun onBackPressed() {
        if (modal.visibility == android.view.View.VISIBLE) {
            AndroidBridge.dialogResolved(false)
            return
        }
        AlertDialog.Builder(this)
            .setTitle("Exit MTKClient?")
            .setMessage("Any active flash operation will be interrupted.")
            .setPositiveButton("Exit") { _, _ ->
                pythonExecutor.execute {
                    try { Python.getInstance().getModule("android_bridge").callAttr("shutdown") } catch (e: Throwable) { }
                }
                finish()
            }
            .setNegativeButton("Cancel", null)
            .show()
    }

    override fun onDestroy() {
        pythonExecutor.shutdownNow()
        super.onDestroy()
    }
}
