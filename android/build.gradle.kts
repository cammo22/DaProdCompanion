// Root build file: dichiara i plugin usati dal modulo app, senza applicarli qui
// (apply false), come da convenzione standard dei progetti Gradle Kotlin DSL
// con un solo modulo applicativo.
plugins {
    id("com.android.application") version "8.5.0" apply false
    id("org.jetbrains.kotlin.android") version "1.9.24" apply false
}
