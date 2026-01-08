package com.tezproje

import java.util.UUID

/**
 * Uygulama (process) ayağa kalktığında oluşan tekil oturum kimliği.
 * Uygulama "görevden kapatılıp" yeniden açıldığında process yeniden başladığı için bu ID değişir.
 */
object AppSession {
    val id: String = UUID.randomUUID().toString()
}



