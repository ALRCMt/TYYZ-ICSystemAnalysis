package top.tyyz2415.cardreader

import android.app.Activity
import android.nfc.NfcAdapter
import android.nfc.Tag
import android.os.Bundle
import android.webkit.JavascriptInterface
import android.webkit.WebView
import android.webkit.WebViewClient
import org.json.JSONObject

/**
 * 只读版安卓壳：WebView 加载 assets/index.html（来自仓库 web/index.html），
 * 把手机 NFC 的读块结果通过 JS 桥回传给网页渲染。
 */
class MainActivity : Activity() {

    private lateinit var webView: WebView
    private var nfcAdapter: NfcAdapter? = null
    private var lastK8: ByteArray? = null
    private var lastK9: ByteArray? = null
    private var reading = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        nfcAdapter = NfcAdapter.getDefaultAdapter(this)

        webView = WebView(this)
        webView.settings.apply {
            javaScriptEnabled = true
            allowFileAccess = true
            domStorageEnabled = true
        }
        webView.webViewClient = WebViewClient()
        webView.addJavascriptInterface(Bridge(), "AndroidNfc")
        webView.loadUrl("file:///android_asset/index.html")
        setContentView(webView)
    }

    override fun onResume() {
        super.onResume()
        nfcAdapter?.enableReaderMode(
            this,
            { tag -> onTagDiscovered(tag) },
            NfcAdapter.FLAG_READER_NFC_A or
                NfcAdapter.FLAG_READER_NFC_B or
                NfcAdapter.FLAG_READER_SKIP_NDEF_CHECK or
                NfcAdapter.FLAG_READER_NO_PLATFORM_SOUNDS,
            null
        )
    }

    override fun onPause() {
        super.onPause()
        try {
            nfcAdapter?.disableReaderMode(this)
        } catch (_: Exception) {
        }
    }

    private fun onTagDiscovered(tag: Tag) {
        if (reading) return
        reading = true
        val k8 = lastK8
        val k9 = lastK9
        Thread {
            val json = try {
                NfcReader().read(tag, k8, k9)
            } catch (e: Exception) {
                val o = JSONObject()
                o.put("error", "读卡失败：" + (e.message ?: e.toString()))
                o.toString()
            }
            runOnUiThread {
                reading = false
                val quoted = JSONObject.quote(json)
                webView.evaluateJavascript(
                    "window.onAndroidNfcResult && window.onAndroidNfcResult($quoted)",
                    null
                )
            }
        }.start()
    }

    /** JS 侧 window.AndroidNfc */
    inner class Bridge {

        @JavascriptInterface
        fun isAvailable(): Boolean = nfcAdapter?.isEnabled == true

        @JavascriptInterface
        fun startRead(keysJson: String) {
            try {
                val obj = JSONObject(keysJson)
                lastK8 = hexToBytes(obj.optString("k8", ""))
                lastK9 = hexToBytes(obj.optString("k9", ""))
            } catch (_: Exception) {
                lastK8 = null
                lastK9 = null
            }
        }

        @JavascriptInterface
        fun ping(): String = "ok"
    }

    private fun hexToBytes(hex: String): ByteArray? {
        if (hex.length != 12) return null
        return try {
            ByteArray(6) { i -> hex.substring(i * 2, i * 2 + 2).toInt(16).toByte() }
        } catch (_: NumberFormatException) {
            null
        }
    }
}
