# Chaquopy / JNI entry points must not be renamed.
-keep class com.chaquo.python.** { *; }
-keep class com.mtkclient.android.AndroidBridge { *; }
-keep class com.mtkclient.android.MainActivity { *; }
-keepattributes *Annotation*
