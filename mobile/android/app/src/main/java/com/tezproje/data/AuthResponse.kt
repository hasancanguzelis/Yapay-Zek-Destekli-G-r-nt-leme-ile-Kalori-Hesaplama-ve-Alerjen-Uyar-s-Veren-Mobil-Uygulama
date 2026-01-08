package com.tezproje.data

data class AuthResponse(
    val access_token: String,
    val token_type: String,
    val username: String
)

