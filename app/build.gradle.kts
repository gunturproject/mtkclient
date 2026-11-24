import java.util.Properties

plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("com.chaquo.python")
}

val versionProps = Properties().apply {
    rootProject.file("version.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}
val appVersionName = versionProps.getProperty("VERSION_NAME", "1.0.0")
val appVersionCode = versionProps.getProperty("VERSION_CODE", "1").toInt()

android {
    namespace = "com.mtkclient.android"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.mtkclient.android"
        minSdk = 24
        targetSdk = 35
        versionCode = appVersionCode
        versionName = appVersionName

        // Chaquopy's Python interpreter is prebuilt; no NDK install is required.
        ndk {
            abiFilters += listOf("arm64-v8a", "x86_64")
        }

        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
    }

    // The CI workflow writes the keystore to SIGNING_KEYSTORE_FILE and passes the
    // passwords through environment variables. Local debug builds stay unsigned-by-release.
    val signingFile = System.getenv("SIGNING_KEYSTORE_FILE")?.takeIf { it.isNotBlank() }?.let { file(it) }
    val signingPass = System.getenv("SIGNING_STORE_PASSWORD")?.takeIf { it.isNotBlank() }
    signingConfigs {
        if (signingFile != null && signingFile.exists() && signingPass != null) {
            create("release") {
                storeFile = signingFile
                storePassword = signingPass
                keyAlias = System.getenv("SIGNING_KEY_ALIAS") ?: "mtkclient-release"
                keyPassword = System.getenv("SIGNING_KEY_PASSWORD") ?: signingPass

                // Sign with all three APK signature schemes so the APK installs on
                // legacy (v1/JAR), modern (v2) and newest (v3) Android verifiers.
                isV1SigningEnabled = true
                isV2SigningEnabled = true
                isV3SigningEnabled = true
            }
        }
        // The debug fallback used when signing secrets are absent gets the same
        // scheme coverage, keeping local CI/test builds installable everywhere.
        getByName("debug") {
            isV1SigningEnabled = true
            isV2SigningEnabled = true
            isV3SigningEnabled = true
        }
    }

    buildTypes {
        getByName("release") {
            isMinifyEnabled = false
            isShrinkResources = false
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            signingConfig = signingConfigs.findByName("release") ?: signingConfigs.getByName("debug")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        viewBinding = true
    }

    packaging {
        resources {
            excludes += setOf("META-INF/LICENSE*", "META-INF/NOTICE*")
        }
    }
}

chaquopy {
    defaultConfig {
        // Upstream mtkclient targets Python >= 3.10; 3.13 has Android wheels for pycryptodomex.
        version = "3.13"

        // Keep upstream .py files on disk: PathConfig resolves loaders/payloads relative to __file__.
        pyc {
            src = false
        }
        extractPackages("mtkclient")

        pip {
            install("pycryptodomex==3.21.0")
            install("colorama")
        }
    }

    sourceSets {
        // Verbatim upstream source. Our Android adapters live in src/main/python and shadow
        // desktop-only modules (usb, serial, capstone, keystone, unicorn, termios, ...).
        getByName("main") {
            srcDir("../upstream")
        }
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.13.1")
    implementation("androidx.appcompat:appcompat:1.7.0")
    implementation("androidx.webkit:webkit:1.12.1")
    implementation("com.google.android.material:material:1.12.0")
}
