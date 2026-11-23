# AW2724DM Monitor Control — Türkçe

[English README](README.md)

Dell Alienware AW2724DM ve DDC/CI destekli diğer monitörlerin giriş kaynağını,
parlaklığını ve kontrastını Ubuntu 26.04 LTS GNOME ortamında yöneten
PyQt6 uygulamasıdır. GNOME Wayland ve X11/Xorg oturumlarını destekler. Donanımla
`ddcutil` üzerinden konuşur; GUI, CLI, GNOME özel klavye kısayolları ve sistem
tepsisi birlikte çalışır.

Qt etkin GNOME oturumuna göre yerel Wayland veya `xcb` arka ucunu otomatik seçer.
DDC/CI iletişimi ekran sunucusundan bağımsızdır. CLI işlemleri grafik oturumuna
ihtiyaç duymaz.

## Proje yapısı

```text
.
├── .github
│   ├── dependabot.yml
│   └── workflows
│       ├── ci.yml
│       └── release.yml
├── apt-requirements.txt
├── install.sh
├── packaging
│   ├── 45-aw2724dm-control-i2c.rules
│   ├── aw2724dm-update
│   ├── aw2724dm-control-launcher
│   ├── aw2724dm-control.desktop
│   ├── i2c-dev.conf
│   └── release-public-key.pem
├── pyproject.toml
├── README.md
├── README_TR.md
├── requirements.txt
├── SECURITY.md
├── src
│   ├── assets
│   │   └── aw2724dm-control.svg
│   └── aw2724dm_control
│       ├── __init__.py
│       ├── __main__.py
│       ├── config.py
│       ├── ddc.py
│       ├── gnome.py
│       ├── gui.py
│       ├── i18n.py
│       ├── logging_config.py
│       ├── main.py
│       ├── shutdown_monitor.py
│       ├── styles.py
│       └── worker.py
├── tests
│   ├── test_ddc.py
│   ├── test_gui_smoke.py
│   ├── test_logging.py
│   ├── test_shutdown_monitor.py
│   └── test_updater.py
└── uninstall.sh
```

## Ön koşullar

- Ubuntu 26.04 LTS ve GNOME Wayland veya X11/Xorg oturumu
- DDC/CI destekli bir monitör
- Monitörün ekran menüsünde DDC/CI seçeneğinin açık olması
- Kurulum sırasında paket indirmek için internet bağlantısı
- `sudo` yetkisi

Etkin GNOME oturumunu şu komutla görebilirsiniz:

```bash
echo "$XDG_SESSION_TYPE"
```

Çıktı `wayland` veya `x11` olabilir; ikisi de desteklenir.

## Tek komutla kurulum

Depo klasöründe:

```bash
chmod +x install.sh uninstall.sh
./install.sh
```

Kurulum betiği şunları otomatik yapar:

1. `apt-requirements.txt` içindeki `ddcutil`, I²C ve Wayland/X11 Qt çalışma
   zamanı paketlerini kurar.
2. `/etc/modules-load.d/i2c-dev.conf` dosyasını oluşturur ve `i2c-dev` modülünü
   hemen yükler.
3. `i2c` grubunu oluşturur, kurulumu başlatan kullanıcıyı bu gruba ekler ve I²C
   aygıtları için grup erişimli udev kuralını kurar.
4. Kullanıcıdan mutlak kurulum dizinini ister; varsayılan olarak
   `/opt/aw2724dm-control` önerilir. Seçilen dizini güvenli izinlerle oluşturur,
   uygulamayı buraya kopyalar ve Python sanal ortamını hazırlar. Etkileşimsiz
   kurulumlarda `AW2724DM_INSTALL_DIR` ortam değişkeni kullanılabilir.
5. `/usr/local/bin/aw2724dm-control` sembolik bağlantısını, uygulama menüsü
   girdisini ve simgeyi kurar.

> **Önemli:** Grup üyeliği çalışan oturuma sonradan eklenemez. Kurulumdan sonra
> GNOME oturumunu tamamen kapatıp yeniden açın; yalnızca terminali kapatıp açmak
> yeterli değildir. Gerekirse bilgisayarı yeniden başlatın.

Yeni oturumda üyeliği ve donanımı sınayın:

```bash
id -nG | tr ' ' '\n' | grep '^i2c$'
ddcutil detect
aw2724dm-control --list
```

## Grafik arayüzü

GNOME uygulama menüsünden **AW2724DM Monitor Control** uygulamasını açın veya:

```bash
aw2724dm-control
```

Başlangıçta uygulama `ddcutil detect` ile monitörleri, her monitör için
`ddcutil capabilities` ile VCP `0x60` giriş değerlerini tarar. İşlemler arayüzü
dondurmamak için iş parçacığı havuzunda yürütülür.

### Dil seçimi

Varsayılan arayüz dili İngilizcedir. **Settings → Language / Dil** menüsünden
**🇬🇧 English** veya **🇹🇷 Türkçe** seçilebilir. Tercih kullanıcı
yapılandırmasına kaydedilir ve uygulama; arayüz, CLI mesajları, güncelleme
pencereleri ve donanım hatalarını yeni dilde göstermek için otomatik yeniden
başlar.

- **Giriş kaynakları:** Algılanan porta tek tıklayarak geçilir.
- **Tanınmayan giriş adları:** Monitör `0x10` kodunu tanımsız bildirirse
  uygulama MCCS standardına göre bunu **DisplayPort-2** olarak gösterir.
- **Hızlı geçiş:** İki farklı giriş seçilir. Seçim hemen yapılandırmaya kaydolur;
  düğme ve `--toggle` aynı çifti kullanır.
- **Parlaklık / kontrast:** Kaydırıcı bırakıldığında sırasıyla VCP `0x10` ve
  `0x12` yazılır.
- **Port takma adları:** Tablonun son sütununa `Ev Bilgisayarı` gibi bir ad yazın.
  Boş bırakırsanız monitörün bildirdiği ad kullanılır.
- **Sistem tepsisi:** Aynı anda yalnızca tek GUI örneği çalışabilir; böylece
  yinelenen veya sahipsiz tepsi simgeleri önlenir. **Settings → Pencere kapanınca
  sistem tepsisinde çalışmaya devam et** seçeneği pencerenin gizlenmesini veya
  uygulamanın gerçekten kapanmasını belirler. Gerçek bir çıkıştan beş saniye
  sonra süreç hâlâ yaşıyorsa watchdog log yazar ve uyarı gösterir.
- **Güncellemeler:** Uygulama açılıştan sonra en son kararlı GitHub Release sürümünü
  asenkron olarak denetler. Denetim en fazla altı saatte bir yapılır. Yeni sürüm
  bulunduğunda kullanıcıdan onay ister. İndirilen sürüm arşivi, SHA-256 özeti ve
  Ed25519 imzası seçilen kurulum dizinindeki `release-public-key.pem` ile doğrulanır;
  doğrulama başarısızsa root kurulumu başlamaz. **Güncellemeleri Denetle** düğmesiyle
  elle denetim de yapılabilir.
- **Güncelleme ilerlemesi:** Yönetici onayı, indirme, SHA-256/Ed25519
  doğrulaması, arşiv açma ve kurulum aşamaları yüzdelik ilerleme çubuğunda
  gösterilir. Uzun `apt`, `pip` ve kurulum çıktıları sonuç penceresine eklenmez;
  log dosyasına yazılır. Başarılı güncellemeden sonra uygulama yeni sürümle
  otomatik yeniden başlar ve ilk kurulumda seçilen dizin korunur.
- **Sürüm ve Hakkında:** Sürüm numarası durum çubuğunda görünür. Ayrıntılar
  için **Yardım → Hakkında** menüsünü veya tepsi menüsünü kullanın.
- **Renkli arayüz:** Giriş, kısayol, güncelleme ve tepsi eylemleri GNOME'un
  açık/koyu temasına uyumlu, birbirinden ayırt edilebilir renkler kullanır.

GNOME Shell, geleneksel tepsi simgelerini kendi başına göstermez. Ubuntu 26.04'te
AppIndicator desteğini sağlayan `gnome-shell-ubuntu-extensions` paketi kurulur.
Simge görünmüyorsa GNOME
oturumunu yeniden başlatın ve Uzantılar uygulamasında **AppIndicator and KStatusNotifierItem Support**
uzantısının etkin olduğunu doğrulayın.

## CLI kullanımı

Genel biçim:

```text
aw2724dm-control [--display NUMARA] İŞLEM
```

Örnekler:

```bash
# Monitörleri ve capabilities çıktısından çözümlenen girişleri göster
aw2724dm-control --list

# Seçili monitörde HDMI 1'e geç
aw2724dm-control --set-input 0x11

# ddcutil ekran 2 üzerinde DisplayPort 1'e geç
aw2724dm-control --display 2 --set-input 0x0f

# GUI'de seçilmiş iki port arasında geç
aw2724dm-control --toggle

# Komutta belirtilen iki port arasında geç
aw2724dm-control --toggle 0x0f 0x11

# Parlaklık ve kontrast ayarla
aw2724dm-control --brightness 70
aw2724dm-control --contrast 65

# Birden fazla ayarı aynı çağrıda uygula
aw2724dm-control --display 1 --brightness 70 --contrast 65
```

Desteklenen tüm seçenekler:

```bash
aw2724dm-control --help
```

Giriş kodları monitörün MCCS capabilities yanıtından alınır. Yaygın değerler
`0x0f` (DisplayPort 1), `0x10` (DisplayPort 2), `0x11` (HDMI 1) ve `0x12`
(HDMI 2) olsa da her monitörde aynı olmak zorunda değildir; önce `--list`
çıktısını kullanın.

## GNOME klavye kısayolu

### Uygulama içinden

1. GUI'de hedef monitörü seçin.
2. **GNOME Kısayolu Ata…** düğmesine basın.
3. Geçiş eylemi için kısayolun kullanacağı iki DisplayPort/HDMI girişini seçin;
   doğrudan geçiş için hedef portu seçin.
4. Kısayol kutusunu seçip istediğiniz tuş birleşimine basın.
5. Onaylayın.

Uygulama `org.gnome.settings-daemon.plugins.media-keys` altındaki boş bir custom
keybinding yolunu bulur, adı/komutu/tuşu yazar ve mevcut kısayolları koruyarak
listeye ekler.

### GNOME Ayarları üzerinden

**Ayarlar → Klavye → Klavye Kısayollarını Görüntüle ve Özelleştir → Özel
Kısayollar** yolunda yeni bir kısayol oluşturun. Komut alanına örneğin:

```bash
aw2724dm-control --display 1 --toggle 0x0f 0x11
```

veya:

```bash
aw2724dm-control --display 1 --set-input 0x11
```

yazın. Bu komutlar GUI açık değilken de çalışır.

## Yapılandırma

Kullanıcı ayarları şurada tutulur:

```text
~/.config/aw2724dm-control/config.json
```

Dosya atomik olarak yazılır ve izinleri `0600` yapılır. Monitör numarası,
port takma adları ve geçiş çiftleri burada saklanır. Uygulama kapalıyken dosyayı
düzenleyebilirsiniz; geçersiz JSON algılanırsa dosya ezilmeden güvenli
varsayılanlarla devam edilir.

## Loglama ve log dışa aktarma

Uygulama kullanımı, DDC hataları, arka plan işlem hataları ve ayrıntılı
güncelleme çıktısı şu dosyaya yazılır:

```text
~/.local/state/aw2724dm-control/aw2724dm-control.log
```

Log 1 MB boyutunda döner ve en fazla beş eski dosya saklanır. Dizin ve dosyalar
yalnızca kullanıcının okuyabileceği izinlerle oluşturulur. **Help/Yardım →
Export Logs…/Logları Dışa Aktar…** seçeneği dönen logları ve temel sistem
bilgisini bir ZIP destek paketine kaydeder. Paket `config.json`, port takma adları
ve klavye kısayolu yapılandırmasını içermez. Donanım ve hata ayrıntıları
bulunabileceği için paylaşmadan önce arşivi inceleyin.

## Sorun giderme

### `Permission denied` veya monitör bulunamıyor

```bash
groups
ls -l /dev/i2c-*
lsmod | grep i2c_dev
ddcutil environment
ddcutil detect
```

Kullanıcı gruplarında `i2c` yoksa oturumu kapatıp açın. Monitör menüsünde DDC/CI
açık olmalıdır. Bazı dizüstü GPU sürücüleri I²C veri yolunu dışarı açmayabilir.

### `Feature 0x60` görünmüyor

Monitör DDC/CI üzerinden giriş değiştirmeyi ilan etmiyor olabilir. Ham çıktıyı
inceleyin:

```bash
ddcutil capabilities --display 1
```

### GUI açılmıyor

```bash
echo "$XDG_SESSION_TYPE"
echo "$DISPLAY"
echo "$WAYLAND_DISPLAY"
```

İlk komut `wayland` veya `x11` döndürebilir. Wayland oturumunda
`WAYLAND_DISPLAY` genellikle `wayland-0`, X11 oturumunda `DISPLAY` genellikle
`:0` veya `:1` olur. Qt çalışma zamanı hatasını görmek için uygulamayı
terminalden `aw2724dm-control` komutuyla başlatın.

### Monitör giriş değişiminden sonra kısa süre yanıt vermiyor

Giriş değişince monitör I²C bağlantısını birkaç saniyeliğine kesebilir. Bu
donanım davranışıdır; birkaç saniye bekleyip yenilemeyi tekrar deneyin.

## Kaldırma

Uygulamayı, masaüstü girdisini ve uygulamaya ait sistem yapılandırmasını kaldırın:

```bash
./uninstall.sh
```

Kullanıcı yapılandırmasını ve logları da silmek için:

```bash
./uninstall.sh --purge
```

Kaldırma betiği `i2c` grubunu ve `apt` paketlerini kaldırmaz; bunlar başka DDC/I²C
uygulamalarında kullanılıyor olabilir. Kullanıcıyı gruptan çıkarmak isterseniz
bunu ayrıca ve bilinçli olarak yapın.

## Güvenlik notları

- Donanım komutlarında `shell=True` kullanılmaz; tüm argümanlar ayrı süreç
  argümanı olarak aktarılır.
- CLI değerleri aralık denetiminden geçirilir.
- GUI donanım işlemleri süre aşımıyla çalışır ve hata çıktısını kullanıcıya
  gösterir.
- Uygulamanın normal çalışması `sudo` istemez. `sudo` yalnızca kurulum ve
  kaldırma sırasında sistem dosyaları için kullanılır.

## Geliştirici testleri

Bağımlılıklar kurulmuş bir sanal ortamda donanım gerektirmeyen parser ve GUI
smoke testlerini çalıştırın:

```bash
PYTHONPATH=src QT_QPA_PLATFORM=offscreen python3 -m unittest discover -s tests -v
```

## İmzalı sürüm yayımlama

Release workflow’u yalnızca `vMAJOR.MINOR.PATCH` biçimli etiketlerde çalışır.
Etiket sürümü hem `src/aw2724dm_control/__init__.py` hem de `pyproject.toml`
içindeki sürümle aynı olmalıdır. İmzalama anahtarı GitHub’da
`RELEASE_SIGNING_PRIVATE_KEY` Actions secret olarak saklanır; özel anahtar repoya
eklenmez.

Yeni sürüm için iki sürüm alanını güncelleyin, testleri çalıştırıp `main` dalına
gönderin ve ardından etiketi yayımlayın:

```bash
git tag -a v1.7.0 -m "AW2724DM Monitor Control 1.7.0"
git push origin v1.7.0
```

GitHub Actions kaynak arşivini deterministik olarak üretir, SHA-256 dosyasını
oluşturur, arşivi Ed25519 ile imzalar, imzayı repodaki açık anahtarla yeniden
doğrular ve üç dosyayı GitHub Release varlığı olarak yayımlar.

Yerel özel anahtar varsayılan olarak
`~/.config/aw2724dm-control/signing/release-private.pem` konumunda `0600`
izinleriyle tutulur. Bu dosyayı güvenli ve çevrimdışı bir konuma yedekleyin;
repoya, Issue'lara veya Release varlıklarına yüklemeyin.
