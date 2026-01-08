package com.tezproje.ui.health

import android.content.Intent
import android.os.Bundle
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.BaseExpandableListAdapter
import android.widget.ExpandableListView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.card.MaterialCardView
import com.tezproje.data.SettingsRepository
import com.tezproje.databinding.ActivityDiseasesBinding
import com.tezproje.ui.MainActivity
import com.tezproje.ui.profile.ProfileActivity
import com.tezproje.ui.settings.SettingsActivity

data class DiseaseInfo(
    val key: String,
    val nameTr: String,
    val nameEn: String,
    val infoTr: String,
    val infoEn: String,
    val adviceTr: String,
    val adviceEn: String
)

class DiseasesActivity : AppCompatActivity() {
    private lateinit var binding: ActivityDiseasesBinding
    private lateinit var adapter: DiseaseExpandableAdapter

    private val diseases = listOf(
        DiseaseInfo(
            key = "diabetes",
            nameTr = "Diyabet",
            nameEn = "Diabetes",
            infoTr = "Diyabet, vücudun kan şekerini düzenleme yeteneğini etkileyen kronik bir hastalıktır. Tip 2 diyabet en yaygın türüdür ve genellikle yaşam tarzı faktörleriyle ilişkilidir.",
            infoEn = "Diabetes is a chronic disease that affects the body's ability to regulate blood sugar. Type 2 diabetes is the most common type and is often associated with lifestyle factors.",
            adviceTr = "• Şekerli ve rafine karbonhidrat içeren gıdalardan kaçının\n• Tam tahıllı ürünleri tercih edin\n• Porsiyon kontrolü yapın\n• Düzenli fiziksel aktivite yapın\n• Lifli gıdalar tüketin (sebze, meyve, baklagiller)\n• İşlenmiş gıdalardan uzak durun",
            adviceEn = "• Avoid foods high in sugar and refined carbohydrates\n• Choose whole grain products\n• Practice portion control\n• Engage in regular physical activity\n• Consume fiber-rich foods (vegetables, fruits, legumes)\n• Avoid processed foods"
        ),
        DiseaseInfo(
            key = "celiac",
            nameTr = "Çölyak Hastalığı",
            nameEn = "Celiac Disease",
            infoTr = "Çölyak hastalığı, gluten tüketimine karşı bağışıklık sisteminin reaksiyon gösterdiği otoimmün bir hastalıktır. Gluten, buğday, arpa ve çavdarda bulunur.",
            infoEn = "Celiac disease is an autoimmune disorder where the immune system reacts to gluten consumption. Gluten is found in wheat, barley, and rye.",
            adviceTr = "• Gluten içeren tüm gıdalardan tamamen kaçının\n• Etiketleri dikkatlice okuyun\n• Glutensiz tahıllar tercih edin (pirinç, mısır, kinoa, karabuğday)\n• Doğal olarak glutensiz gıdalar tüketin (meyve, sebze, et, balık, yumurta)\n• Çapraz bulaşmaya dikkat edin",
            adviceEn = "• Completely avoid all foods containing gluten\n• Read labels carefully\n• Choose gluten-free grains (rice, corn, quinoa, buckwheat)\n• Consume naturally gluten-free foods (fruits, vegetables, meat, fish, eggs)\n• Be careful about cross-contamination"
        ),
        DiseaseInfo(
            key = "hypertension",
            nameTr = "Hipertansiyon",
            nameEn = "Hypertension",
            infoTr = "Hipertansiyon, kan basıncının sürekli olarak yüksek seyretmesi durumudur. Kalp hastalığı ve felç riskini artırır.",
            infoEn = "Hypertension is a condition where blood pressure is consistently high. It increases the risk of heart disease and stroke.",
            adviceTr = "• Tuz ve sodyum alımını azaltın\n• DASH diyetini uygulayın (sebze, meyve, tam tahıl)\n• İşlenmiş gıdalardan kaçının\n• Potasyum açısından zengin gıdalar tüketin (muz, avokado, ıspanak)\n• Alkol tüketimini sınırlandırın\n• Düzenli egzersiz yapın",
            adviceEn = "• Reduce salt and sodium intake\n• Follow the DASH diet (vegetables, fruits, whole grains)\n• Avoid processed foods\n• Consume potassium-rich foods (bananas, avocados, spinach)\n• Limit alcohol consumption\n• Exercise regularly"
        ),
        DiseaseInfo(
            key = "hypercholesterolemia",
            nameTr = "Yüksek Kolesterol",
            nameEn = "High Cholesterol",
            infoTr = "Yüksek kolesterol, kanda kolesterol seviyesinin normalin üzerinde olması durumudur. Kalp hastalığı riskini artırır.",
            infoEn = "High cholesterol is a condition where cholesterol levels in the blood are above normal. It increases the risk of heart disease.",
            adviceTr = "• Doymuş yağ alımını azaltın\n• Trans yağlardan kaçının\n• Omega-3 açısından zengin gıdalar tüketin (balık, ceviz)\n• Lifli gıdalar tüketin (yulaf, meyve, sebze)\n• Kızartmalardan kaçının\n• Zeytinyağı gibi sağlıklı yağlar kullanın",
            adviceEn = "• Reduce saturated fat intake\n• Avoid trans fats\n• Consume omega-3 rich foods (fish, walnuts)\n• Eat fiber-rich foods (oats, fruits, vegetables)\n• Avoid fried foods\n• Use healthy fats like olive oil"
        ),
        DiseaseInfo(
            key = "kidney_disease",
            nameTr = "Böbrek Hastalığı",
            nameEn = "Kidney Disease",
            infoTr = "Böbrek hastalığı, böbreklerin işlevlerini yerine getirememesi durumudur. Beslenme, böbrek sağlığı için kritik öneme sahiptir.",
            infoEn = "Kidney disease is a condition where the kidneys cannot perform their functions. Nutrition is critical for kidney health.",
            adviceTr = "• Protein alımını doktor önerisine göre sınırlandırın\n• Sodyum ve tuz alımını azaltın\n• Potasyum ve fosfor içeren gıdalara dikkat edin\n• Sıvı alımını doktor önerisine göre ayarlayın\n• İşlenmiş gıdalardan kaçının\n• Taze sebze ve meyve tercih edin",
            adviceEn = "• Limit protein intake according to doctor's recommendation\n• Reduce sodium and salt intake\n• Be careful with potassium and phosphorus-containing foods\n• Adjust fluid intake according to doctor's recommendation\n• Avoid processed foods\n• Prefer fresh vegetables and fruits"
        ),
        DiseaseInfo(
            key = "liver_disease",
            nameTr = "Karaciğer Hastalığı",
            nameEn = "Liver Disease",
            infoTr = "Karaciğer hastalığı, karaciğerin işlevlerini yerine getirememesi durumudur. Alkol, yağlı gıdalar ve bazı ilaçlar karaciğere zarar verebilir.",
            infoEn = "Liver disease is a condition where the liver cannot perform its functions. Alcohol, fatty foods, and some medications can damage the liver.",
            adviceTr = "• Alkol tüketiminden tamamen kaçının\n• Yağlı ve kızartılmış gıdalardan kaçının\n• Şekerli içeceklerden uzak durun\n• Protein alımını dengeli tutun\n• Taze sebze ve meyve tüketin\n• İşlenmiş gıdalardan kaçının",
            adviceEn = "• Completely avoid alcohol consumption\n• Avoid fatty and fried foods\n• Stay away from sugary drinks\n• Keep protein intake balanced\n• Consume fresh vegetables and fruits\n• Avoid processed foods"
        ),
        DiseaseInfo(
            key = "heart_disease",
            nameTr = "Kalp Hastalığı",
            nameEn = "Heart Disease",
            infoTr = "Kalp hastalığı, kalbin işlevlerini etkileyen çeşitli durumları kapsar. Sağlıklı beslenme kalp sağlığı için çok önemlidir.",
            infoEn = "Heart disease covers various conditions that affect heart function. Healthy eating is very important for heart health.",
            adviceTr = "• Doymuş ve trans yağlardan kaçının\n• Omega-3 açısından zengin gıdalar tüketin (balık, ceviz)\n• Tuz ve sodyum alımını azaltın\n• Lifli gıdalar tüketin\n• Kızartmalardan kaçının\n• Sebze ve meyve ağırlıklı beslenin",
            adviceEn = "• Avoid saturated and trans fats\n• Consume omega-3 rich foods (fish, walnuts)\n• Reduce salt and sodium intake\n• Eat fiber-rich foods\n• Avoid fried foods\n• Eat a diet rich in vegetables and fruits"
        ),
        DiseaseInfo(
            key = "obesity",
            nameTr = "Obezite",
            nameEn = "Obesity",
            infoTr = "Obezite, vücut kitle indeksinin normalin üzerinde olması durumudur. Sağlıklı beslenme ve düzenli egzersiz ile yönetilebilir.",
            infoEn = "Obesity is a condition where body mass index is above normal. It can be managed with healthy eating and regular exercise.",
            adviceTr = "• Kalori alımını kontrol edin\n• Porsiyon boyutlarına dikkat edin\n• Şekerli içeceklerden kaçının\n• Lifli gıdalar tüketin\n• Düzenli fiziksel aktivite yapın\n• İşlenmiş ve fast food gıdalardan uzak durun",
            adviceEn = "• Control calorie intake\n• Pay attention to portion sizes\n• Avoid sugary drinks\n• Consume fiber-rich foods\n• Engage in regular physical activity\n• Stay away from processed and fast food"
        ),
        DiseaseInfo(
            key = "reflux",
            nameTr = "Reflü",
            nameEn = "Reflux",
            infoTr = "Reflü, mide asidinin yemek borusuna geri kaçması durumudur. Bazı gıdalar reflüyü tetikleyebilir.",
            infoEn = "Reflux is a condition where stomach acid flows back into the esophagus. Some foods can trigger reflux.",
            adviceTr = "• Baharatlı ve asitli gıdalardan kaçının\n• Kafeinli içecekleri sınırlandırın\n• Çikolata ve yağlı gıdalardan uzak durun\n• Küçük ve sık öğünler tüketin\n• Yemekten sonra hemen yatmayın\n• Alkol tüketimini azaltın",
            adviceEn = "• Avoid spicy and acidic foods\n• Limit caffeinated drinks\n• Stay away from chocolate and fatty foods\n• Eat small and frequent meals\n• Don't lie down immediately after eating\n• Reduce alcohol consumption"
        ),
        DiseaseInfo(
            key = "ibs",
            nameTr = "IBS (Huzursuz Bağırsak Sendromu)",
            nameEn = "IBS (Irritable Bowel Syndrome)",
            infoTr = "IBS, bağırsak fonksiyonlarını etkileyen kronik bir durumdur. Belirtiler kişiden kişiye değişir.",
            infoEn = "IBS is a chronic condition that affects bowel function. Symptoms vary from person to person.",
            adviceTr = "• FODMAP diyetini deneyin (düşük FODMAP gıdalar)\n• Lif alımını yavaşça artırın\n• Soğan, sarımsak gibi tetikleyicilerden kaçının\n• Stres yönetimi yapın\n• Düzenli yemek saatleri oluşturun\n• Bol su için",
            adviceEn = "• Try the FODMAP diet (low FODMAP foods)\n• Gradually increase fiber intake\n• Avoid triggers like onions, garlic\n• Manage stress\n• Establish regular meal times\n• Drink plenty of water"
        ),
        DiseaseInfo(
            key = "gout",
            nameTr = "Gut (Ürik Asit)",
            nameEn = "Gout",
            infoTr = "Gut, ürik asit kristallerinin eklemlerde birikmesi sonucu oluşan ağrılı bir durumdur. Pürin içeren gıdalar ürik asidi artırabilir.",
            infoEn = "Gout is a painful condition caused by the accumulation of uric acid crystals in joints. Foods containing purines can increase uric acid.",
            adviceTr = "• Pürin içeren gıdalardan kaçının (sakatat, bazı deniz ürünleri)\n• Alkol tüketimini sınırlandırın\n• Bol su için\n• Kiraz tüketin (anti-inflamatuar)\n• Şekerli içeceklerden uzak durun\n• Düşük yağlı süt ürünleri tercih edin",
            adviceEn = "• Avoid purine-containing foods (organ meats, some seafood)\n• Limit alcohol consumption\n• Drink plenty of water\n• Consume cherries (anti-inflammatory)\n• Stay away from sugary drinks\n• Prefer low-fat dairy products"
        ),
        DiseaseInfo(
            key = "lactose_intolerance",
            nameTr = "Laktoz İntoleransı",
            nameEn = "Lactose Intolerance",
            infoTr = "Laktoz intoleransı, süt şekeri olan laktozu sindirememe durumudur. Süt ve süt ürünleri tüketildiğinde rahatsızlık oluşur.",
            infoEn = "Lactose intolerance is the inability to digest lactose, the sugar in milk. Discomfort occurs when consuming milk and dairy products.",
            adviceTr = "• Laktoz içeren süt ürünlerinden kaçının\n• Laktozsuz alternatifleri tercih edin\n• Kalsiyum kaynaklarını artırın (yeşil yapraklı sebzeler, badem)\n• Etiketleri okuyun (laktoz içerip içermediğini kontrol edin)\n• Küçük miktarlarda deneyerek toleransınızı test edin\n• Probiyotik takviyeleri düşünün",
            adviceEn = "• Avoid dairy products containing lactose\n• Prefer lactose-free alternatives\n• Increase calcium sources (leafy greens, almonds)\n• Read labels (check if it contains lactose)\n• Test your tolerance by trying small amounts\n• Consider probiotic supplements"
        )
    )

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        SettingsRepository(applicationContext).applyToApp()
        binding = ActivityDiseasesBinding.inflate(layoutInflater)
        setContentView(binding.root)

        adapter = DiseaseExpandableAdapter(diseases, isTurkish())
        binding.diseasesExpandableList.setAdapter(adapter)

        // Bottom Navigation
        binding.bottomNav.selectedItemId = com.tezproje.R.id.nav_health
        binding.bottomNav.setOnItemSelectedListener { item ->
            when (item.itemId) {
                com.tezproje.R.id.nav_analyze -> {
                    startActivity(Intent(this, MainActivity::class.java))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_health -> true
                com.tezproje.R.id.nav_assistant -> {
                    startActivity(Intent(this, com.tezproje.ui.assistant.AssistantActivity::class.java))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_profile -> {
                    startActivity(Intent(this, ProfileActivity::class.java))
                    finish()
                    true
                }
                com.tezproje.R.id.nav_settings -> {
                    startActivity(Intent(this, SettingsActivity::class.java))
                    finish()
                    true
                }
                else -> false
            }
        }
    }

    private fun isTurkish(): Boolean {
        val lang = try {
            resources.configuration.locales[0]?.language
        } catch (_: Exception) {
            null
        } ?: java.util.Locale.getDefault().language
        return lang.lowercase().startsWith("tr")
    }
}

class DiseaseExpandableAdapter(
    private val diseases: List<DiseaseInfo>,
    private val isTurkish: Boolean
) : BaseExpandableListAdapter() {

    override fun getGroupCount(): Int = diseases.size

    override fun getChildrenCount(groupPosition: Int): Int = 1

    override fun getGroup(groupPosition: Int): DiseaseInfo = diseases[groupPosition]

    override fun getChild(groupPosition: Int, childPosition: Int): DiseaseInfo = diseases[groupPosition]

    override fun getGroupId(groupPosition: Int): Long = groupPosition.toLong()

    override fun getChildId(groupPosition: Int, childPosition: Int): Long = childPosition.toLong()

    override fun hasStableIds(): Boolean = true

    override fun getGroupView(
        groupPosition: Int,
        isExpanded: Boolean,
        convertView: View?,
        parent: ViewGroup?
    ): View {
        val view = convertView ?: LayoutInflater.from(parent?.context).inflate(
            com.tezproje.R.layout.item_disease_group,
            parent,
            false
        )

        val disease = getGroup(groupPosition)
        val nameText = view.findViewById<TextView>(com.tezproje.R.id.diseaseNameText)
        val expandIcon = view.findViewById<android.widget.ImageView>(com.tezproje.R.id.expandIcon)

        nameText.text = if (isTurkish) disease.nameTr else disease.nameEn
        expandIcon.rotation = if (isExpanded) 180f else 0f

        return view
    }

    override fun getChildView(
        groupPosition: Int,
        childPosition: Int,
        isLastChild: Boolean,
        convertView: View?,
        parent: ViewGroup?
    ): View {
        val view = convertView ?: LayoutInflater.from(parent?.context).inflate(
            com.tezproje.R.layout.item_disease_child,
            parent,
            false
        )

        val disease = getChild(groupPosition, childPosition)
        val infoText = view.findViewById<TextView>(com.tezproje.R.id.diseaseInfoText)
        val adviceText = view.findViewById<TextView>(com.tezproje.R.id.dietAdviceText)

        if (isTurkish) {
            infoText.text = disease.infoTr
            adviceText.text = disease.adviceTr
        } else {
            infoText.text = disease.infoEn
            adviceText.text = disease.adviceEn
        }

        return view
    }

    override fun isChildSelectable(groupPosition: Int, childPosition: Int): Boolean = false
}

