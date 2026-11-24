package com.mtkclient.android

import android.app.Activity
import android.app.AlertDialog
import android.content.Context
import android.content.Intent
import android.hardware.usb.UsbConstants
import android.hardware.usb.UsbDevice
import android.hardware.usb.UsbDeviceConnection
import android.hardware.usb.UsbEndpoint
import android.hardware.usb.UsbInterface
import android.hardware.usb.UsbManager
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.DocumentsContract
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.view.Gravity
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.Toast
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.io.File
import java.io.FileInputStream
import java.io.FileOutputStream
import java.util.Base64
import java.util.Locale
import java.util.concurrent.Callable
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger

/** Static Java façade called from the Chaquopy Python layer. */
object AndroidBridge {

    private const val REQ_OPEN = 4301
    private const val REQ_SAVE = 4302
    private const val REQ_DIR = 4303
    private const val REQ_USB_PERMISSION = 4304

    private var appContext: Context? = null
    private var activityRef: Activity? = null

    private val usbManager: UsbManager?
        get() = appContext?.getSystemService(Context.USB_SERVICE) as? UsbManager

    private val connections = mutableMapOf<String, UsbDeviceConnection>()
    private val claimed = mutableMapOf<String, MutableList<UsbInterface>>()
    private val serialHandles = mutableMapOf<String, SerialHandle>()

    private var resultLatch: CountDownLatch? = null
    private var resultCode = Activity.RESULT_CANCELED
    private var resultData: Intent? = null
    private var pendingMode = ""

    private val dialogLatch = AtomicInteger(0)
    private var dialogAnswer = false
    private var promptAnswer = ""
    private var pendingSavePath: File? = null

    fun init(context: Context, activity: Activity) {
        appContext = context.applicationContext
        activityRef = activity
    }

    // ------------------------------------------------------------------
    // UI helpers used by the Python compatibility layer
    // ------------------------------------------------------------------
    @JvmStatic fun runOnUiThread(runnable: Runnable) {
        activityRef?.runOnUiThread(runnable)
    }

    @JvmStatic fun isDarkMode(): Boolean {
        val mask = appContext?.resources?.configuration?.uiMode?.and(
            android.content.res.Configuration.UI_MODE_NIGHT_MASK)
        return mask == android.content.res.Configuration.UI_MODE_NIGHT_YES
    }

    @JvmStatic fun hasRoot(): Boolean = try {
        val p = Runtime.getRuntime().exec(arrayOf("su", "-c", "id -u"))
        val out = p.inputStream.bufferedReader().readLine()?.trim()
        p.waitFor(3, TimeUnit.SECONDS)
        out == "0"
    } catch (e: Exception) {
        false
    }

    @JvmStatic fun openUrl(url: String) {
        try {
            val i = Intent(Intent.ACTION_VIEW, Uri.parse(url))
            i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            appContext?.startActivity(i)
        } catch (e: Exception) {
            toast("Cannot open $url")
        }
    }

    @JvmStatic fun showMessage(kind: String, title: String, text: String): Int {
        val act = activityRef ?: return 0
        val latch = CountDownLatch(1)
        val answer = intArrayOf(0)
        act.runOnUiThread {
            val builder = AlertDialog.Builder(act)
                .setTitle(title)
                .setMessage(text)
                .setCancelable(kind != "error")
            when (kind) {
                "confirm" -> builder
                    .setPositiveButton("Yes") { _, _ -> answer[0] = 2; latch.countDown() }
                    .setNegativeButton("No") { _, _ -> answer[0] = 4; latch.countDown() }
                else -> builder.setPositiveButton("OK") { _, _ -> answer[0] = 1; latch.countDown() }
            }
            builder.setOnCancelListener { latch.countDown() }
            builder.show()
        }
        try { latch.await(5, TimeUnit.MINUTES) } catch (e: InterruptedException) { }
        return answer[0]
    }

    @JvmStatic fun prompt(title: String, label: String, default: String): String {
        val act = activityRef ?: return ""
        val latch = CountDownLatch(1)
        val result = arrayOf("")
        act.runOnUiThread {
            val input = EditText(act)
            input.setText(default)
            input.setSelection(input.text.length)
            val wrap = LinearLayout(act).apply {
                orientation = LinearLayout.VERTICAL
                setPadding(48, 16, 48, 16)
                addView(input)
            }
            AlertDialog.Builder(act)
                .setTitle(title)
                .setMessage(label)
                .setView(wrap)
                .setPositiveButton("OK") { _, _ -> result[0] = input.text.toString(); latch.countDown() }
                .setNegativeButton("Cancel") { _, _ -> latch.countDown() }
                .setOnCancelListener { latch.countDown() }
                .show()
        }
        try { latch.await(5, TimeUnit.MINUTES) } catch (e: InterruptedException) { }
        return result[0]
    }

    @JvmStatic fun showDialog(html: String) {
        activityRef?.runOnUiThread { (activityRef as? MainActivity)?.showModal(html) }
    }

    @JvmStatic fun closeDialog() {
        activityRef?.runOnUiThread { (activityRef as? MainActivity)?.hideModal() }
    }

    @JvmStatic fun waitForDialog(id: String): Boolean {
        val latch = CountDownLatch(1)
        dialogLatch.incrementAndGet()
        activityRef?.runOnUiThread {
            (activityRef as? MainActivity)?.setDialogCallback {
                dialogAnswer = true
                latch.countDown()
            }
            (activityRef as? MainActivity)?.setDialogCancelCallback { latch.countDown() }
        }
        try { latch.await(10, TimeUnit.MINUTES) } catch (e: InterruptedException) { }
        return dialogAnswer
    }

    @JvmStatic fun dialogResolved(accepted: Boolean) {
        if (accepted) {
            (activityRef as? MainActivity)?.resolveDialog(true)
        } else {
            (activityRef as? MainActivity)?.resolveDialog(false)
        }
    }

    // ------------------------------------------------------------------
    // File picker
    // ------------------------------------------------------------------
    @JvmStatic fun pickFile(mode: String, caption: String, directory: String, filter: String): String {
        val act = activityRef ?: return ""
        pendingMode = mode
        val latch = CountDownLatch(1)
        resultLatch = latch
        val intent = when (mode) {
            "save" -> {
                val name = filter.substringAfter("(").substringBefore(")").trim()
                    .ifBlank { "dump.bin" }.split(";").first().trim().ifBlank { "dump.bin" }
                pendingSavePath = File(act.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS), name)
                Intent(Intent.ACTION_CREATE_DOCUMENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "*/*"
                    putExtra(Intent.EXTRA_TITLE, name)
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                        putExtra(DocumentsContract.EXTRA_INITIAL_URI, pendingSavePath?.toURI())
                    }
                }
            }
            "dir" -> Intent(Intent.ACTION_OPEN_DOCUMENT_TREE)
            else -> Intent(Intent.ACTION_OPEN_DOCUMENT).apply {
                addCategory(Intent.CATEGORY_OPENABLE)
                type = "*/*"
            }
        }
        act.runOnUiThread {
            try {
                act.startActivityForResult(intent, when (mode) {
                    "save" -> REQ_SAVE
                    "dir" -> REQ_DIR
                    else -> REQ_OPEN
                })
            } catch (e: Exception) {
                toast("File picker unavailable: ${e.message}")
                latch.countDown()
            }
        }
        try { latch.await(10, TimeUnit.MINUTES) } catch (e: InterruptedException) { }
        resultLatch = null
        return handlePickerResult(mode, resultCode, resultData)
    }

    fun onActivityResult(requestCode: Int, code: Int, data: Intent?) {
        resultCode = code
        resultData = data
        resultLatch?.countDown()
    }

    private fun handlePickerResult(mode: String, code: Int, data: Intent?): String {
        if (code != Activity.RESULT_OK || data?.data == null) return ""
        val uri: Uri = data.data ?: return ""
        val ctx = appContext ?: return ""
        try {
            ctx.contentResolver.takePersistableUriPermission(
                uri, Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_GRANT_WRITE_URI_PERMISSION)
        } catch (e: Exception) { }
        if (mode == "dir") return uri.toString()

        val name = queryName(ctx, uri) ?: "download.bin"
        if (mode == "save") {
            pendingSavePath?.let { source ->
                if (source.exists()) {
                    ctx.contentResolver.openOutputStream(uri)?.use { out ->
                        FileInputStream(source).use { it.copyTo(out) }
                    }
                    return source.absolutePath
                }
            }
            return uri.toString()
        }

        val target = File(ctx.cacheDir, "picker/$name")
        target.parentFile?.mkdirs()
        ctx.contentResolver.openInputStream(uri)?.use { input ->
            FileOutputStream(target).use { input.copyTo(it) }
        }
        return target.absolutePath
    }

    private fun queryName(context: Context, uri: Uri): String? {
        var name: String? = null
        try {
            context.contentResolver.query(uri, arrayOf(OpenableColumns.DISPLAY_NAME), null, null, null)?.use { c ->
                if (c.moveToFirst()) {
                    val i = c.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                    if (i >= 0) name = c.getString(i)
                }
            }
        } catch (e: Exception) { }
        if (name == null && uri.scheme == "content") {
            name = DocumentsContract.getDocumentId(uri).substringAfterLast(':')
        }
        if (name == null) name = uri.lastPathSegment
        return name
    }

    // ------------------------------------------------------------------
    // USB host
    // ------------------------------------------------------------------
    @JvmStatic fun listUsbDevices(): String {
        val array = JSONArray()
        val manager = usbManager ?: return array.toString()
        for (device in manager.deviceList.values) {
            val obj = JSONObject().apply {
                put("deviceId", device.deviceName)
                put("vendorId", device.vendorId)
                put("productId", device.productId)
                put("deviceClass", device.deviceClass)
                put("deviceSubClass", device.deviceSubclass)
                put("deviceProtocol", device.deviceProtocol)
                put("deviceAddress", device.deviceAddress)
                put("busNumber", device.busNumber)
                put("productName", device.productName ?: "")
                put("manufacturerName", device.manufacturerName ?: "")
                put("serialNumber", device.serialNumber ?: "")
                put("configuration", configurationJson(device.getConfiguration(0)))
            }
            array.put(obj)
        }
        return array.toString()
    }

    private fun endpointAddress(endpoint: UsbEndpoint): Int {
        val num = endpoint.endpointNumber
        return if (endpoint.direction == UsbConstants.USB_DIR_IN) (0x80 or num) else num
    }

    private fun configurationJson(config: android.hardware.usb.UsbConfiguration?): JSONObject {
        val obj = JSONObject()
        val interfaces = JSONArray()
        if (config != null) {
            obj.put("configurationValue", config.id)
            obj.put("configurationName", config.name ?: "")
            for (i in 0 until config.interfaceCount) {
                val itf = config.getInterface(i)
                val ia = JSONObject().apply {
                    put("interfaceNumber", itf.id)
                    put("alternateSetting", itf.alternateSetting)
                    put("interfaceClass", itf.interfaceClass)
                    put("interfaceSubClass", itf.interfaceSubclass)
                    put("interfaceProtocol", itf.interfaceProtocol)
                    put("interfaceName", itf.name ?: "")
                }
                val endpoints = JSONArray()
                for (e in 0 until itf.endpointCount) {
                    val ep = itf.getEndpoint(e)
                    endpoints.put(JSONObject().apply {
                        put("endpointAddress", endpointAddress(ep))
                        put("maxPacketSize", ep.maxPacketSize)
                        put("bmAttributes", ep.type)
                        put("interval", ep.interval)
                    })
                }
                ia.put("endpoints", endpoints)
                interfaces.put(ia)
            }
        } else {
            obj.put("configurationValue", 1)
            val fallback = JSONObject().apply {
                put("interfaceNumber", 0)
                put("interfaceClass", 255)
                put("endpoints", JSONArray().put(JSONObject().put("endpointAddress", 0x81).put("maxPacketSize", 512))
                    .put(JSONObject().put("endpointAddress", 0x01).put("maxPacketSize", 512)))
            }
            interfaces.put(fallback)
        }
        obj.put("interfaces", interfaces)
        return obj
    }

    private fun findDevice(deviceId: String): UsbDevice? =
        usbManager?.deviceList?.values?.firstOrNull { it.deviceName == deviceId }

    private fun openConnection(deviceId: String): UsbDeviceConnection? {
        connections[deviceId]?.let { return it }
        val manager = usbManager ?: return null
        val device = findDevice(deviceId) ?: return null
        if (!manager.hasPermission(device)) {
            val latch = CountDownLatch(1)
            val act = activityRef
            if (act == null) return null
            act.runOnUiThread {
                try {
                    val pi = android.app.PendingIntent.getActivity(
                        act, 0, act.intent,
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
                            android.app.PendingIntent.FLAG_MUTABLE else 0)
                    manager.requestPermission(device, pi)
                } catch (e: Exception) { }
                latch.countDown()
            }
            try { latch.await(2, TimeUnit.SECONDS) } catch (e: InterruptedException) { }
            if (!manager.hasPermission(device)) return null
        }
        val connection = manager.openDevice(device) ?: return null
        connections[deviceId] = connection
        claimAll(device, connection)
        return connection
    }

    private fun claimAll(device: UsbDevice, connection: UsbDeviceConnection) {
        val list = claimed.getOrPut(device.deviceName) { mutableListOf() }
        if (list.isNotEmpty()) return
        for (i in 0 until device.configurationCount) {
            val config = device.getConfiguration(i) ?: continue
            for (j in 0 until config.interfaceCount) {
                val itf = config.getInterface(j)
                if (connection.claimInterface(itf, true)) list.add(itf)
            }
            break
        }
    }

    @JvmStatic fun usbSetConfiguration(deviceId: String, value: Int): Boolean {
        val connection = openConnection(deviceId) ?: return false
        val ok = connection.setConfiguration(value)
        findDevice(deviceId)?.let { claimAll(it, connection) }
        return ok
    }

    @JvmStatic fun usbBulkWrite(deviceId: String, endpoint: Int, data: ByteArray, timeout: Int): Int {
        val connection = openConnection(deviceId) ?: return -1
        val ep = findEndpoint(deviceId, endpoint) ?: return -1
        return connection.bulkTransfer(ep, data, data.size, timeout)
    }

    @JvmStatic fun usbBulkRead(deviceId: String, endpoint: Int, size: Int, timeout: Int): ByteArray {
        val connection = openConnection(deviceId) ?: return ByteArray(0)
        val ep = findEndpoint(deviceId, endpoint) ?: return ByteArray(0)
        val buffer = ByteArray(size.coerceAtMost(1 shl 20))
        val n = connection.bulkTransfer(ep, buffer, buffer.size, timeout)
        return if (n > 0) buffer.copyOf(n) else ByteArray(0)
    }

    private fun findEndpoint(deviceId: String, address: Int): UsbEndpoint? {
        val device = findDevice(deviceId) ?: return null
        for (i in 0 until device.configurationCount) {
            val config = device.getConfiguration(i) ?: continue
            for (j in 0 until config.interfaceCount) {
                val itf = config.getInterface(j)
                for (k in 0 until itf.endpointCount) {
                    val ep = itf.getEndpoint(k)
                    if (endpointAddress(ep) == address) return ep
                }
            }
        }
        return null
    }

    @JvmStatic fun usbControlIn(deviceId: String, requestType: Int, request: Int,
                                value: Int, index: Int, length: Int, timeout: Int): ByteArray {
        val connection = openConnection(deviceId) ?: return ByteArray(0)
        val buffer = ByteArray(length.coerceAtLeast(0).coerceAtMost(65536))
        val n = connection.controlTransfer(requestType, request, value, index, buffer, buffer.size, timeout)
        return if (n > 0) buffer.copyOf(n) else ByteArray(0)
    }

    @JvmStatic fun usbControlOut(deviceId: String, requestType: Int, request: Int,
                                 value: Int, index: Int, data: ByteArray, timeout: Int): Int {
        val connection = openConnection(deviceId) ?: return -1
        return connection.controlTransfer(requestType, request, value, index, data, data.size, timeout)
    }

    @JvmStatic fun usbClearHalt(deviceId: String, endpoint: Int): Boolean {
        val ep = findEndpoint(deviceId, endpoint) ?: return false
        return connections[deviceId]?.clearHalt(ep) ?: false
    }

    @JvmStatic fun usbReset(deviceId: String): Boolean = connections[deviceId]?.reset() ?: false

    @JvmStatic fun requestUsbPermission(deviceId: String): Boolean {
        val manager = usbManager ?: return false
        val device = findDevice(deviceId) ?: return false
        if (manager.hasPermission(device)) return true
        val act = activityRef ?: return false
        val latch = CountDownLatch(1)
        act.runOnUiThread {
            try {
                val pi = android.app.PendingIntent.getActivity(
                    act, 0, act.intent,
                    if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S)
                        android.app.PendingIntent.FLAG_MUTABLE else 0)
                manager.requestPermission(device, pi)
            } catch (e: Exception) { }
            latch.countDown()
        }
        try { latch.await(30, TimeUnit.SECONDS) } catch (e: InterruptedException) { }
        return manager.hasPermission(device)
    }

    // ------------------------------------------------------------------
    // Serial ports (root shell)
    // ------------------------------------------------------------------
    @JvmStatic fun listSerialPorts(): String {
        val array = JSONArray()
        val dev = File("/dev")
        val names = dev.listFiles()?.map { it.name }?.filter {
            it.startsWith("ttyUSB") || it.startsWith("ttyACM") || it.startsWith("ttyS")
        }?.sorted() ?: emptyList()
        for (name in names) {
            val path = "/dev/$name"
            val info = sysfsValue(name, "idVendor") to sysfsValue(name, "idProduct")
            val vid = info.first?.toIntOrNull(16) ?: 0
            val pid = info.second?.toIntOrNull(16) ?: 0
            array.put(JSONObject().apply {
                put("device", path)
                put("name", name)
                put("description", sysfsValue(name, "product") ?: "Serial port")
                put("manufacturer", sysfsValue(name, "manufacturer") ?: "")
                put("vendorId", vid)
                put("productId", pid)
            })
        }
        return array.toString()
    }

    private fun sysfsValue(name: String, key: String): String? {
        val candidates = listOf(
            "/sys/class/tty/$name/device/$key",
            "/sys/class/tty/$name/device/../../$key",
            "/sys/class/tty/$name/../../$key"
        )
        for (path in candidates) {
            try {
                val f = File(path)
                if (f.exists()) return f.readText().trim()
            } catch (e: Exception) { }
        }
        return null
    }

    private class SerialHandle(val path: String, val process: Process)

    @JvmStatic fun serialOpen(port: String, baud: Int, bytesize: Int, parity: String, stopbits: Float): String {
        serialHandles[port]?.let { return port }
        if (!File(port).exists()) return ""
        return try {
            stty(port, baud, bytesize, parity, stopbits)
            val process = ProcessBuilder("su", "-c", "cat $port")
                .redirectErrorStream(false)
                .start()
            serialHandles[port] = SerialHandle(port, process)
            port
        } catch (e: Exception) {
            ""
        }
    }

    private fun stty(port: String, baud: Int, bytesize: Int, parity: String, stopbits: Float) {
        val parityFlag = when (parity) {
            "E" -> "parenb -parodd"
            "O" -> "parenb parodd"
            else -> "-parenb"
        }
        val bits = if (bytesize == 8) "cs8" else "cs7"
        val stop = if (stopbits >= 2f) "cstopb" else "-cstopb"
        try {
            Runtime.getRuntime().exec(arrayOf("su", "-c", "stty -F $port $baud $bits $parityFlag $stop raw -echo"))
                .waitFor(2, TimeUnit.SECONDS)
        } catch (e: Exception) { }
    }

    @JvmStatic fun serialClose(handle: String): Boolean {
        val h = serialHandles.remove(handle) ?: return false
        try { h.process.destroy() } catch (e: Exception) { }
        return true
    }

    @JvmStatic fun serialWrite(handle: String, data: ByteArray): Int {
        val h = serialHandles[handle] ?: return -1
        val encoded = android.util.Base64.encodeToString(data, android.util.Base64.NO_WRAP)
        return try {
            val p = Runtime.getRuntime().exec(
                arrayOf("su", "-c", "printf %s $encoded | base64 -d > ${h.path}"))
            p.outputStream.close()
            p.waitFor(5, TimeUnit.SECONDS)
            data.size
        } catch (e: Exception) { -1 }
    }

    @JvmStatic fun serialRead(handle: String, size: Int, timeout: Int): ByteArray {
        val h = serialHandles[handle] ?: return ByteArray(0)
        val stream = h.process.inputStream
        val deadline = System.nanoTime() + timeout * 1_000_000L
        val out = ByteArrayOutputStream()
        while (out.size() < size && System.nanoTime() < deadline) {
            val available = stream.available()
            if (available > 0) {
                val buffer = ByteArray(minOf(size - out.size(), available))
                val n = stream.read(buffer)
                if (n > 0) out.write(buffer, 0, n)
            } else {
                Thread.sleep(5)
            }
        }
        return out.toByteArray()
    }

    @JvmStatic fun serialAvailable(handle: String): Int =
        serialHandles[handle]?.process?.inputStream?.available() ?: 0

    @JvmStatic fun serialDiscardInput(handle: String) {
        val h = serialHandles[handle] ?: return
        try { h.process.inputStream.skip(Long.MAX_VALUE) } catch (e: Exception) { }
    }

    @JvmStatic fun serialSendBreak(handle: String, duration: Float) {
        val h = serialHandles[handle] ?: return
        try {
            Runtime.getRuntime().exec(arrayOf("su", "-c", "stty -F ${h.path} brkint"))
        } catch (e: Exception) { }
    }

    @JvmStatic fun serialSetSignals(handle: String, rts: Boolean?, dtr: Boolean?) {
        // Root tty ioctl control would require a native helper; signal state is
        // stored by the Python shim and applied where the USB CDC path supports it.
    }

    // ------------------------------------------------------------------
    // Optional native-tool providers (absent by default; Python falls back)
    // ------------------------------------------------------------------
    @JvmStatic fun asm(arch: Int, mode: Int, codeJson: String): String? = null
    @JvmStatic fun disasm(arch: Int, mode: Int, code: ByteArray, address: Int): String? = null

    private fun toast(message: String) {
        activityRef?.runOnUiThread {
            Toast.makeText(appContext, message, Toast.LENGTH_SHORT).show()
        }
    }
}
