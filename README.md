# ContextLite — Microsoft Foundry Local ile Yerel RAG Asistanı

ContextLite; PDF, TXT ve Markdown belgelerini cihazda indeksleyen, ilgili parçaları
bulan ve yanıtı Microsoft Foundry Local modeliyle yine cihazda üreten bir web
uygulamasıdır. Temel akış internet servisi veya API anahtarı gerektirmez.

## Projenin amacı

Projenin sertifika için ana senaryosu şudur:

1. Kullanıcı bir proje oluşturur ve belge yükler.
2. Metin, örtüşmeli küçük parçalara ayrılır.
3. Foundry Local embedding modeli her parçayı sayısal vektöre dönüştürür.
4. Metin, embedding ve kaynak bilgisi SQLite'ta saklanır.
5. Soru embedding'i ile en yakın üç parça bulunur.
6. Bu parçalar Foundry Local sohbet modeline bağlam olarak verilir.
7. Yanıt, dosya ve sayfa kaynaklarıyla kullanıcıya gösterilir.

Embedding modeli geçici olarak kullanılamazsa uygulama kapanmaz; tamamen yerel
SQLite FTS5 kelime aramasına geri döner. Mesajın altında **Anlamsal RAG** veya
**Kelime araması** etiketi hangi yolun kullanıldığını açıkça gösterir.

## Gereksinimler

- Windows 10/11
- Python 3.11 veya daha yeni sürüm
- İlk bağımlılık/model indirmesi için internet
- Önerilen: 16 GB RAM; daha düşük bellekte küçük bir Foundry modeli seçilebilir

Uygulama resmi `foundry-local-sdk` paketini ve güncel
`FoundryLocalManager.initialize(...)` / `FoundryLocalManager.instance` akışını
kullanır. Yeni Windows 11 cihazlarda WinML varyantı ek hızlandırma sağlayabilir;
standart paket Windows 10 ile daha geniş CPU uyumluluğu için seçilmiştir.

## En hızlı çalıştırma

PowerShell'de proje klasörünü açıp:

```powershell
powershell -ExecutionPolicy Bypass -File .\start.ps1
```

Ardından <http://127.0.0.1:8124/app> adresini açın. İlk açılışta sahip hesabını
oluşturun. Şifreleme anahtarı `data/.encryption_key` altında otomatik ve yerel
olarak oluşturulur; Git'e eklenmez.

Elle kurulum gerekirse:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn src.main:app --port 8124
```

## Beş dakikalık sunum akışı

Hazır Türkçe uygulama demosu: [ContextLite 5 Dakikalık Tanıtım Videosu](./ContextLite_5_Dakika_Tanitim_FINAL.mp4)

1. Ana ekranda gizlilik ve sıfır API maliyeti hedefini anlatın.
2. Ayarlar'da **Foundry Local → Bağlantıyı Test Et** düğmesine basın. Bu test
   yalnızca model listesine bakmaz, gerçek bir inference çalıştırır.
3. `Projeler` bölümünde örneğin “Ders Notları” adlı bir proje oluşturup kısa bir
   PDF yükleyin.
4. Projeyi açın ve belgede cevabı açıkça bulunan bir soru sorun.
5. Yanıttaki kaynak/sayfa bilgisini ve **Anlamsal RAG** etiketini gösterin.
6. Aynı belgede olmayan bir şey sorun; asistanın bilgi uydurmak yerine belgede
   bulunamadığını söylediğini gösterin.
7. İnterneti kapatıp ikinci bir soru sorarak yerel çalışmayı kanıtlayın.

## Model seçimi

Sohbette **Otomatik model (önerilen)** seçimi önce yüklü, sonra önbellekteki en
uygun modeli kullanır. Genel cevap kalitesini artırmak için `.env` dosyasında
şunlar seçilebilir:

```dotenv
FOUNDRY_CHAT_MODEL=phi-3.5-mini
FOUNDRY_EMBEDDING_MODEL=qwen3-embedding-0.6b
```

Sidebar'daki **Modeller** sayfası Foundry kataloğundaki sohbet modellerini,
indirme boyutlarını ve kurulum durumlarını listeler. **Kur** düğmesi seçilen
modeli resmi SDK ile arka planda indirir ve ilerlemeyi yüzde olarak gösterir;
aynı anda yalnızca bir indirme çalıştırılır.

Küçük modeller hızlıdır fakat ChatGPT düzeyinde genel bilgi doğruluğu beklenmez.
Bu projenin doğruluk stratejisi daha büyük bir modeli taklit etmek değil; cevabı
yüklenen belgeyle sınırlandırmak, ilgili parçayı anlamsal olarak bulmak ve kaynağı
göstermektir.

## Mimari

```text
Tarayıcı (HTML/CSS/JS)
        │  REST + SSE
        ▼
FastAPI ── sohbet geçmişi / kullanıcı / proje
        │
        ├── SQLite: belge parçaları + embedding JSON + FTS5
        │
        └── Microsoft Foundry Local SDK
              ├── qwen3-embedding-0.6b (arama)
              └── yerel sohbet modeli (yanıt)
```

## Sorun giderme

- **Python bulunamadı:** Python 3.11+ kurun; kurulum ekranında “Add Python to
  PATH” seçeneğini açın.
- **İlk cevap gecikiyor:** Model ilk kez indiriliyor/yükleniyor olabilir. Sonraki
  cevaplar daha hızlıdır.
- **Model bulunamadı:** `.env` içindeki model adını kaldırıp otomatik seçimi
  kullanın veya Ayarlar'daki listeden görünen bir model seçin.
- **Kelime araması etiketi çıkıyor:** Embedding modeli yüklenememiştir. Terminal
  çıktısını kontrol edin, sonra belgeyi yeniden yükleyin.
- **Boş/ulaşılamıyor:** Önce `/health`, sonra Ayarlar'daki gerçek inference
  testini kontrol edin. Backend artık SDK ve model hatasını sohbet içinde açıkça
  döndürür.

## Kaynaklar

- [Microsoft Foundry Local — Python başlangıç rehberi](https://learn.microsoft.com/windows/ai/foundry-local/get-started)
- [Microsoft Foundry Local resmi SDK ve örnekleri](https://github.com/microsoft/Foundry-Local)
- [Microsoft yerel RAG örneği](https://techcommunity.microsoft.com/blog/azuredevcommunityblog/building-your-first-local-rag-application-with-foundry-local/4501968)
