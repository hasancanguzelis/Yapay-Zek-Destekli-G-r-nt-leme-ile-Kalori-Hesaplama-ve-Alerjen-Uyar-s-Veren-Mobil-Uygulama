package com.tezproje.ui.profile

import com.tezproje.data.UserProfile

data class ProfileUiState(
    val profile: UserProfile = UserProfile(),
    val savedMessage: String? = null,
    val errorMessage: String? = null
)






