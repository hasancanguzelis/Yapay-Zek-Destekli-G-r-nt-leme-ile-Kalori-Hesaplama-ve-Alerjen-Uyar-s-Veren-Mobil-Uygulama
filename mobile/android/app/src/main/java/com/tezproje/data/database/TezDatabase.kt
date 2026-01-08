package com.tezproje.data.database

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.room.TypeConverters

@Database(
    entities = [ProfileEntity::class, AnalysisResultEntity::class],
    version = 1,
    exportSchema = false
)
@TypeConverters(Converters::class)
abstract class TezDatabase : RoomDatabase() {
    abstract fun profileDao(): ProfileDao
    abstract fun analysisResultDao(): AnalysisResultDao
    
    companion object {
        @Volatile
        private var INSTANCE: TezDatabase? = null
        
        fun getDatabase(context: Context): TezDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    TezDatabase::class.java,
                    "tez_database"
                )
                    .fallbackToDestructiveMigration() // Development için, production'da migration yapılmalı
                    .build()
                INSTANCE = instance
                instance
            }
        }
    }
}
