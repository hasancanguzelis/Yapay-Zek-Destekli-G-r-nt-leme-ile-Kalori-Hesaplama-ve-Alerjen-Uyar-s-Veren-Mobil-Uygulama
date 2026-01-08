package com.tezproje.data.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query
import androidx.room.Update

@Dao
interface ProfileDao {
    @Query("SELECT * FROM user_profiles WHERE username = :username LIMIT 1")
    suspend fun getProfile(username: String): ProfileEntity?
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertProfile(profile: ProfileEntity)
    
    @Update
    suspend fun updateProfile(profile: ProfileEntity)
    
    @Query("DELETE FROM user_profiles WHERE username = :username")
    suspend fun deleteProfile(username: String)
}
