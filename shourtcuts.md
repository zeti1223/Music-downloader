# ⌨️ Billentyűparancsok és Parancsok

A program Vim-szerű vezérlést használ. A parancsok beírásához nyomd meg a `:` gombot.

## 🧭 Navigáció
 **`j`**: Lefelé lépés a listában
 **`k`**: Felfelé lépés a listában
 **`:`**: Parancssor megnyitása (fókuszálás)

## 🛠 Parancsok
A parancssorba (`:`) írhatod be az alábbiakat:

 **`:add <link>`** - Zene vagy playlist hozzáadása (pl. `:add https://spotify...`)
 **`:start`** - Letöltés indítása
 **`:pause`** - Letöltés szüneteltetése / folytatása
 **`:abort`** - Folyamat megszakítása
 **`:clear`** - Letöltési lista törlése
 **`:save`** - Beállítások mentése (Settings fülön lévő szöveg alapján)
 **`:q`** - Kilépés a programból
 **`:queue`** - Váltás a "Queue" (Lista) nézetre
 **`:log`** - Váltás a "Log" (Napló) nézetre
 **`:settings`** - Váltás a "Settings" (Beállítások) nézetre

## ⚙️ Beállítások formátuma
A Settings fülön egy szöveges fájlt szerkeszthetsz. A minőség (`quality`) formátuma:
- `mp3-1` -> MP3 128kbps
- `mp3-2` -> MP3 256kbps
- `mp3-3` -> MP3 320kbps
- `webm`, `ogg`, `m4a`, `flac` -> Egyéb formátumok
