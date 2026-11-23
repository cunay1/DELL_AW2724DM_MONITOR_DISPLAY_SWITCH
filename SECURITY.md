# Güvenlik Politikası

## Desteklenen sürümler

Yalnızca en son kararlı GitHub Release sürümü güvenlik güncellemeleri alır.

## Güvenlik açığı bildirme

Bir güvenlik açığını herkese açık Issue olarak paylaşmayın. Deponun **Security →
Report a vulnerability** bölümündeki özel bildirim formunu kullanın. Bildirime
etkilenen sürümü, yeniden üretme adımlarını ve olası etkiyi ekleyin.

## Güncelleme güvenliği

Kararlı sürüm arşivleri Ed25519 ile imzalanır. Uygulama, indirilen arşivin hem
SHA-256 özetini hem de `packaging/release-public-key.pem` açık anahtarıyla dijital
imzasını doğrulamadan güncellemeyi kurmaz.
