plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "top.tyyz2415.cardreader"
    compileSdk = 34
    buildToolsVersion = "34.0.0"

    defaultConfig {
        applicationId = "top.tyyz2415.cardreader"
        minSdk = 21
        targetSdk = 34
        versionCode = 4
        versionName = "0.4-readonly"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }
}

// 构建前把仓库里的 web/index.html 同步到 assets，保证网页只有一份源码
val syncWebAssets by tasks.registering(Copy::class) {
    from(rootProject.file("../web/index.html"))
    into(layout.projectDirectory.dir("src/main/assets"))
}
tasks.named("preBuild") { dependsOn(syncWebAssets) }




