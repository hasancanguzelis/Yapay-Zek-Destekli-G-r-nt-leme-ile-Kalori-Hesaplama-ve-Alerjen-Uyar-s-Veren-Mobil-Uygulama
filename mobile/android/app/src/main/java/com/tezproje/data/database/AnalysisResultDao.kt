package com.tezproje.data.database

import androidx.room.Dao
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.Query

@Dao
interface AnalysisResultDao {
    @Query("SELECT * FROM analysis_results WHERE username = :username ORDER BY createdAt DESC LIMIT :limit")
    suspend fun getRecentResults(username: String?, limit: Int = 10): List<AnalysisResultEntity>
    
    @Query("SELECT * FROM analysis_results WHERE id = :id LIMIT 1")
    suspend fun getResultById(id: Long): AnalysisResultEntity?
    
    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun insertResult(result: AnalysisResultEntity): Long
    
    @Query("DELETE FROM analysis_results WHERE id = :id")
    suspend fun deleteResult(id: Long)
    
    @Query("DELETE FROM analysis_results WHERE username = :username")
    suspend fun deleteAllResultsForUser(username: String)
    
    @Query("DELETE FROM analysis_results WHERE createdAt < :beforeTimestamp")
    suspend fun deleteOldResults(beforeTimestamp: Long)
}
