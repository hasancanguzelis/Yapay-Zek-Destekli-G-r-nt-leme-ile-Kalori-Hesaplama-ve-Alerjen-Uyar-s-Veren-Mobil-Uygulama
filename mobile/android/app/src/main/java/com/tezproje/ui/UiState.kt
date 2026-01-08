package com.tezproje.ui

import com.tezproje.data.AnalyzeResponse

sealed class UiState {
    data object Idle : UiState()
    data object Loading : UiState()
    data class Success(val data: AnalyzeResponse) : UiState()
    data class Error(val message: String) : UiState()
}






