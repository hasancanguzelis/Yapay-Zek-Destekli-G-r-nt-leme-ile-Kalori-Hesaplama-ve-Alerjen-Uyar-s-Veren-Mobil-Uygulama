package com.tezproje.network

import com.tezproje.data.AnalyzeResponse
import com.tezproje.data.AssistantResponse
import com.tezproje.data.CalorieTargetResponse
import com.tezproje.data.DailyConsumptionResponse
import com.tezproje.data.NutritionFacts
import okhttp3.MultipartBody
import okhttp3.RequestBody
import com.tezproje.data.UserProfile
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.Field
import retrofit2.http.FormUrlEncoded
import retrofit2.http.GET
import retrofit2.http.Header
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

interface TezApiService {
    @Multipart
    @POST("analyze")
    suspend fun analyze(
        @Part image: MultipartBody.Part,
        @Part("lang") lang: RequestBody?,
        @Part("barcode") barcode: RequestBody?,
        @Part("user_profile_json") userProfileJson: RequestBody?,
        @Part("ui_lang") uiLang: RequestBody?
    ): AnalyzeResponse

    @FormUrlEncoded
    @POST("product/by_barcode")
    suspend fun productByBarcode(
        @Field("barcode") barcode: String,
        @Field("user_profile_json") userProfileJson: String?,
        @Field("ui_lang") uiLang: String?
    ): AnalyzeResponse

    @Multipart
    @POST("meal/analyze")
    suspend fun analyzeMeal(
        @Part image: MultipartBody.Part,
        @Part("dish_name") dishName: RequestBody?,
        @Part("ingredients_csv") ingredientsCsv: RequestBody?,
        @Part("user_profile_json") userProfileJson: RequestBody?,
        @Part("ui_lang") uiLang: RequestBody?
    ): AnalyzeResponse

    @FormUrlEncoded
    @POST("meal/predict")
    suspend fun predictMeal(
        @Field("dish_name") dishName: String,
        @Field("portion") portion: String?,
        @Field("user_profile_json") userProfileJson: String?,
        @Field("ui_lang") uiLang: String?
    ): AnalyzeResponse

    @FormUrlEncoded
    @POST("meal/estimate")
    suspend fun estimateMeal(
        @Field("dish_name") dishName: String,
        @Field("portion") portion: String?,
        @Field("user_profile_json") userProfileJson: String?,
        @Field("ui_lang") uiLang: String?
    ): AnalyzeResponse

    @FormUrlEncoded
    @POST("assistant/chat")
    suspend fun assistantChat(
        @Field("message") message: String,
        @Field("ui_lang") uiLang: String?
    ): AssistantResponse

    @Multipart
    @POST("analyze/image_calories")
    suspend fun analyzeImageCalories(
        @Part image: MultipartBody.Part,
        @Part("user_profile_json") userProfileJson: RequestBody?,
        @Part("ui_lang") uiLang: RequestBody?
    ): AnalyzeResponse

    @FormUrlEncoded
    @POST("auth/register")
    suspend fun register(
        @Field("username") username: String,
        @Field("password") password: String
    ): com.tezproje.data.AuthResponse

    @FormUrlEncoded
    @POST("auth/login")
    suspend fun login(
        @Field("username") username: String,
        @Field("password") password: String
    ): com.tezproje.data.AuthResponse

    @GET("profile")
    suspend fun getProfile(
        @Header("Authorization") authorization: String
    ): UserProfile

    @PUT("profile")
    suspend fun updateProfile(
        @Header("Authorization") authorization: String,
        @Body profile: UserProfile
    ): UserProfile

    @GET("calorie/target")
    suspend fun getCalorieTarget(
        @Header("Authorization") authorization: String,
        @retrofit2.http.Query("goal") goal: String = "maintain"
    ): CalorieTargetResponse

    @POST("consumption/add")
    suspend fun addConsumption(
        @Header("Authorization") authorization: String,
        @Body nutrition: NutritionFacts,
        @retrofit2.http.Query("consumption_date") consumptionDate: String? = null
    ): DailyConsumptionResponse

    @GET("consumption/today")
    suspend fun getTodayConsumption(
        @Header("Authorization") authorization: String
    ): DailyConsumptionResponse

    @GET("consumption/{date}")
    suspend fun getConsumptionByDate(
        @Header("Authorization") authorization: String,
        @retrofit2.http.Path("date") date: String
    ): DailyConsumptionResponse

    @retrofit2.http.DELETE("consumption/{date}")
    suspend fun deleteConsumption(
        @Header("Authorization") authorization: String,
        @retrofit2.http.Path("date") date: String
    ): retrofit2.Response<Unit>
}


