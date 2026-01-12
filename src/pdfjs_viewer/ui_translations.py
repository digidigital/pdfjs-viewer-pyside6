"""Translations for general UI messages.

Supports automatic language detection based on system locale.
Includes clipboard, error messages, and other user-facing text.
"""

import locale
from typing import Dict

# Translation dictionaries for each supported language
TRANSLATIONS = {
    'en': {  # English (US/UK)
        'text_copied': 'Copied to clipboard',
        'clipboard_error': 'Clipboard error: {error}',
        # File dialogs
        'save_pdf_title': 'Save PDF',
        'open_pdf_title': 'Open PDF',
        'select_stamp_title': 'Select Stamp Image',
        'pdf_files_filter': 'PDF Files (*.pdf);;All Files (*)',
        'image_files_filter': 'Images (*.png *.jpg *.jpeg *.gif *.bmp);;All Files (*)',
        # External link confirmation
        'open_link_title': 'Open External Link',
        'open_link_message': 'Open this link in your browser?\n\n{url}',
    },
    'de': {  # German
        'text_copied': 'In Zwischenablage kopiert',
        'clipboard_error': 'Zwischenablagefehler: {error}',
        # File dialogs
        'save_pdf_title': 'PDF speichern',
        'open_pdf_title': 'PDF öffnen',
        'select_stamp_title': 'Stempelbild auswählen',
        'pdf_files_filter': 'PDF-Dateien (*.pdf);;Alle Dateien (*)',
        'image_files_filter': 'Bilder (*.png *.jpg *.jpeg *.gif *.bmp);;Alle Dateien (*)',
        # External link confirmation
        'open_link_title': 'Externen Link öffnen',
        'open_link_message': 'Diesen Link im Browser öffnen?\n\n{url}',
    },
    'fr': {  # French
        'text_copied': 'Copié dans le presse-papiers',
        'clipboard_error': 'Erreur du presse-papiers: {error}',
        # File dialogs
        'save_pdf_title': 'Enregistrer le PDF',
        'open_pdf_title': 'Ouvrir le PDF',
        'select_stamp_title': 'Sélectionner une image de tampon',
        'pdf_files_filter': 'Fichiers PDF (*.pdf);;Tous les fichiers (*)',
        'image_files_filter': 'Images (*.png *.jpg *.jpeg *.gif *.bmp);;Tous les fichiers (*)',
        # External link confirmation
        'open_link_title': 'Ouvrir le lien externe',
        'open_link_message': 'Ouvrir ce lien dans votre navigateur?\n\n{url}',
    },
    'es': {  # Spanish
        'text_copied': 'Copiado al portapapeles',
        'clipboard_error': 'Error del portapapeles: {error}',
        # File dialogs
        'save_pdf_title': 'Guardar PDF',
        'open_pdf_title': 'Abrir PDF',
        'select_stamp_title': 'Seleccionar imagen de sello',
        'pdf_files_filter': 'Archivos PDF (*.pdf);;Todos los archivos (*)',
        'image_files_filter': 'Imágenes (*.png *.jpg *.jpeg *.gif *.bmp);;Todos los archivos (*)',
        # External link confirmation
        'open_link_title': 'Abrir enlace externo',
        'open_link_message': '¿Abrir este enlace en su navegador?\n\n{url}',
    },
    'it': {  # Italian
        'text_copied': 'Copiato negli appunti',
        'clipboard_error': 'Errore degli appunti: {error}',
        # File dialogs
        'save_pdf_title': 'Salva PDF',
        'open_pdf_title': 'Apri PDF',
        'select_stamp_title': 'Seleziona immagine timbro',
        'pdf_files_filter': 'File PDF (*.pdf);;Tutti i file (*)',
        'image_files_filter': 'Immagini (*.png *.jpg *.jpeg *.gif *.bmp);;Tutti i file (*)',
        # External link confirmation
        'open_link_title': 'Apri link esterno',
        'open_link_message': 'Aprire questo link nel browser?\n\n{url}',
    },
    'pt': {  # Portuguese
        'text_copied': 'Copiado para a área de transferência',
        'clipboard_error': 'Erro da área de transferência: {error}',
        # File dialogs
        'save_pdf_title': 'Salvar PDF',
        'open_pdf_title': 'Abrir PDF',
        'select_stamp_title': 'Selecionar imagem de carimbo',
        'pdf_files_filter': 'Arquivos PDF (*.pdf);;Todos os arquivos (*)',
        'image_files_filter': 'Imagens (*.png *.jpg *.jpeg *.gif *.bmp);;Todos os arquivos (*)',
        # External link confirmation
        'open_link_title': 'Abrir link externo',
        'open_link_message': 'Abrir este link no navegador?\n\n{url}',
    },
    'nl': {  # Dutch
        'text_copied': 'Gekopieerd naar klembord',
        'clipboard_error': 'Klembordfout: {error}',
        # File dialogs
        'save_pdf_title': 'PDF opslaan',
        'open_pdf_title': 'PDF openen',
        'select_stamp_title': 'Stempelafbeelding selecteren',
        'pdf_files_filter': 'PDF-bestanden (*.pdf);;Alle bestanden (*)',
        'image_files_filter': 'Afbeeldingen (*.png *.jpg *.jpeg *.gif *.bmp);;Alle bestanden (*)',
        # External link confirmation
        'open_link_title': 'Externe link openen',
        'open_link_message': 'Deze link openen in uw browser?\n\n{url}',
    },
    'pl': {  # Polish
        'text_copied': 'Skopiowano do schowka',
        'clipboard_error': 'Błąd schowka: {error}',
        # File dialogs
        'save_pdf_title': 'Zapisz PDF',
        'open_pdf_title': 'Otwórz PDF',
        'select_stamp_title': 'Wybierz obraz pieczątki',
        'pdf_files_filter': 'Pliki PDF (*.pdf);;Wszystkie pliki (*)',
        'image_files_filter': 'Obrazy (*.png *.jpg *.jpeg *.gif *.bmp);;Wszystkie pliki (*)',
        # External link confirmation
        'open_link_title': 'Otwórz link zewnętrzny',
        'open_link_message': 'Otworzyć ten link w przeglądarce?\n\n{url}',
    },
    'cs': {  # Czech
        'text_copied': 'Zkopírováno do schránky',
        'clipboard_error': 'Chyba schránky: {error}',
        # File dialogs
        'save_pdf_title': 'Uložit PDF',
        'open_pdf_title': 'Otevřít PDF',
        'select_stamp_title': 'Vybrat obrázek razítka',
        'pdf_files_filter': 'Soubory PDF (*.pdf);;Všechny soubory (*)',
        'image_files_filter': 'Obrázky (*.png *.jpg *.jpeg *.gif *.bmp);;Všechny soubory (*)',
        # External link confirmation
        'open_link_title': 'Otevřít externí odkaz',
        'open_link_message': 'Otevřít tento odkaz v prohlížeči?\n\n{url}',
    },
    'sv': {  # Swedish
        'text_copied': 'Kopierat till urklipp',
        'clipboard_error': 'Urklippsfel: {error}',
        # File dialogs
        'save_pdf_title': 'Spara PDF',
        'open_pdf_title': 'Öppna PDF',
        'select_stamp_title': 'Välj stämpelbild',
        'pdf_files_filter': 'PDF-filer (*.pdf);;Alla filer (*)',
        'image_files_filter': 'Bilder (*.png *.jpg *.jpeg *.gif *.bmp);;Alla filer (*)',
        # External link confirmation
        'open_link_title': 'Öppna extern länk',
        'open_link_message': 'Öppna denna länk i din webbläsare?\n\n{url}',
    },
    'da': {  # Danish
        'text_copied': 'Kopieret til udklipsholder',
        'clipboard_error': 'Udklipsholderfejl: {error}',
        # File dialogs
        'save_pdf_title': 'Gem PDF',
        'open_pdf_title': 'Åbn PDF',
        'select_stamp_title': 'Vælg stempelbillede',
        'pdf_files_filter': 'PDF-filer (*.pdf);;Alle filer (*)',
        'image_files_filter': 'Billeder (*.png *.jpg *.jpeg *.gif *.bmp);;Alle filer (*)',
        # External link confirmation
        'open_link_title': 'Åbn eksternt link',
        'open_link_message': 'Åbn dette link i din browser?\n\n{url}',
    },
    'no': {  # Norwegian
        'text_copied': 'Kopiert til utklippstavle',
        'clipboard_error': 'Utklippstavlefeil: {error}',
        # File dialogs
        'save_pdf_title': 'Lagre PDF',
        'open_pdf_title': 'Åpne PDF',
        'select_stamp_title': 'Velg stempelbilde',
        'pdf_files_filter': 'PDF-filer (*.pdf);;Alle filer (*)',
        'image_files_filter': 'Bilder (*.png *.jpg *.jpeg *.gif *.bmp);;Alle filer (*)',
        # External link confirmation
        'open_link_title': 'Åpne ekstern lenke',
        'open_link_message': 'Åpne denne lenken i nettleseren?\n\n{url}',
    },
    'fi': {  # Finnish
        'text_copied': 'Kopioitu leikepöydälle',
        'clipboard_error': 'Leikepöytävirhe: {error}',
        # File dialogs
        'save_pdf_title': 'Tallenna PDF',
        'open_pdf_title': 'Avaa PDF',
        'select_stamp_title': 'Valitse leimakuva',
        'pdf_files_filter': 'PDF-tiedostot (*.pdf);;Kaikki tiedostot (*)',
        'image_files_filter': 'Kuvat (*.png *.jpg *.jpeg *.gif *.bmp);;Kaikki tiedostot (*)',
        # External link confirmation
        'open_link_title': 'Avaa ulkoinen linkki',
        'open_link_message': 'Avataanko tämä linkki selaimessa?\n\n{url}',
    },
    'el': {  # Greek
        'text_copied': 'Αντιγράφηκε στο πρόχειρο',
        'clipboard_error': 'Σφάλμα προχείρου: {error}',
        # File dialogs
        'save_pdf_title': 'Αποθήκευση PDF',
        'open_pdf_title': 'Άνοιγμα PDF',
        'select_stamp_title': 'Επιλογή εικόνας σφραγίδας',
        'pdf_files_filter': 'Αρχεία PDF (*.pdf);;Όλα τα αρχεία (*)',
        'image_files_filter': 'Εικόνες (*.png *.jpg *.jpeg *.gif *.bmp);;Όλα τα αρχεία (*)',
        # External link confirmation
        'open_link_title': 'Άνοιγμα εξωτερικού συνδέσμου',
        'open_link_message': 'Άνοιγμα αυτού του συνδέσμου στο πρόγραμμα περιήγησης;\n\n{url}',
    },
    'uk': {  # Ukrainian
        'text_copied': 'Скопійовано в буфер обміну',
        'clipboard_error': 'Помилка буфера обміну: {error}',
        # File dialogs
        'save_pdf_title': 'Зберегти PDF',
        'open_pdf_title': 'Відкрити PDF',
        'select_stamp_title': 'Вибрати зображення печатки',
        'pdf_files_filter': 'Файли PDF (*.pdf);;Всі файли (*)',
        'image_files_filter': 'Зображення (*.png *.jpg *.jpeg *.gif *.bmp);;Всі файли (*)',
        # External link confirmation
        'open_link_title': 'Відкрити зовнішнє посилання',
        'open_link_message': 'Відкрити це посилання у браузері?\n\n{url}',
    },
    'hi': {  # Hindi
        'text_copied': 'क्लिपबोर्ड में कॉपी किया गया',
        'clipboard_error': 'क्लिपबोर्ड त्रुटि: {error}',
        # File dialogs
        'save_pdf_title': 'PDF सहेजें',
        'open_pdf_title': 'PDF खोलें',
        'select_stamp_title': 'स्टाम्प छवि चुनें',
        'pdf_files_filter': 'PDF फ़ाइलें (*.pdf);;सभी फ़ाइलें (*)',
        'image_files_filter': 'छवियाँ (*.png *.jpg *.jpeg *.gif *.bmp);;सभी फ़ाइलें (*)',
        # External link confirmation
        'open_link_title': 'बाहरी लिंक खोलें',
        'open_link_message': 'इस लिंक को अपने ब्राउज़र में खोलें?\n\n{url}',
    },
    'ro': {  # Romanian
        'text_copied': 'Copiat în clipboard',
        'clipboard_error': 'Eroare clipboard: {error}',
        # File dialogs
        'save_pdf_title': 'Salvare PDF',
        'open_pdf_title': 'Deschide PDF',
        'select_stamp_title': 'Selectare imagine ștampilă',
        'pdf_files_filter': 'Fișiere PDF (*.pdf);;Toate fișierele (*)',
        'image_files_filter': 'Imagini (*.png *.jpg *.jpeg *.gif *.bmp);;Toate fișierele (*)',
        # External link confirmation
        'open_link_title': 'Deschide link extern',
        'open_link_message': 'Deschideți acest link în browser?\n\n{url}',
    },
    'hu': {  # Hungarian
        'text_copied': 'Vágólapra másolva',
        'clipboard_error': 'Vágólap hiba: {error}',
        # File dialogs
        'save_pdf_title': 'PDF mentése',
        'open_pdf_title': 'PDF megnyitása',
        'select_stamp_title': 'Bélyegző kép kiválasztása',
        'pdf_files_filter': 'PDF fájlok (*.pdf);;Minden fájl (*)',
        'image_files_filter': 'Képek (*.png *.jpg *.jpeg *.gif *.bmp);;Minden fájl (*)',
        # External link confirmation
        'open_link_title': 'Külső link megnyitása',
        'open_link_message': 'Megnyitja ezt a linket a böngészőben?\n\n{url}',
    },
    'bg': {  # Bulgarian
        'text_copied': 'Копирано в клипборда',
        'clipboard_error': 'Грешка в клипборда: {error}',
        # File dialogs
        'save_pdf_title': 'Запазване на PDF',
        'open_pdf_title': 'Отваряне на PDF',
        'select_stamp_title': 'Избор на изображение за печат',
        'pdf_files_filter': 'PDF файлове (*.pdf);;Всички файлове (*)',
        'image_files_filter': 'Изображения (*.png *.jpg *.jpeg *.gif *.bmp);;Всички файлове (*)',
        # External link confirmation
        'open_link_title': 'Отваряне на външна връзка',
        'open_link_message': 'Отваряне на тази връзка в браузъра?\n\n{url}',
    },
    'hr': {  # Croatian
        'text_copied': 'Kopirano u međuspremnik',
        'clipboard_error': 'Greška međuspremnika: {error}',
        # File dialogs
        'save_pdf_title': 'Spremi PDF',
        'open_pdf_title': 'Otvori PDF',
        'select_stamp_title': 'Odaberi sliku pečata',
        'pdf_files_filter': 'PDF datoteke (*.pdf);;Sve datoteke (*)',
        'image_files_filter': 'Slike (*.png *.jpg *.jpeg *.gif *.bmp);;Sve datoteke (*)',
        # External link confirmation
        'open_link_title': 'Otvori vanjsku poveznicu',
        'open_link_message': 'Otvoriti ovu poveznicu u pregledniku?\n\n{url}',
    },
    'zh': {  # Chinese (Simplified)
        'text_copied': '已复制到剪贴板',
        'clipboard_error': '剪贴板错误: {error}',
        # File dialogs
        'save_pdf_title': '保存PDF',
        'open_pdf_title': '打开PDF',
        'select_stamp_title': '选择图章图像',
        'pdf_files_filter': 'PDF文件 (*.pdf);;所有文件 (*)',
        'image_files_filter': '图像 (*.png *.jpg *.jpeg *.gif *.bmp);;所有文件 (*)',
        # External link confirmation
        'open_link_title': '打开外部链接',
        'open_link_message': '在浏览器中打开此链接?\n\n{url}',
    },
}

class SafeDict(dict):
    def __missing__(self, key):
        return "Translation missing"

def get_translations(lang_code: str = None) -> Dict[str, str]:
    if lang_code is None:
        try:
            system_locale = locale.getdefaultlocale()[0]
            if system_locale:
                lang_code = system_locale.split('_')[0].lower()
        except (AttributeError, IndexError):
            lang_code = 'en'

    # Pick the correct translation dict (fallback to English)
    base = TRANSLATIONS.get(lang_code, TRANSLATIONS['en'])

    # Wrap it in SafeDict
    return SafeDict(base)


def get_available_languages() -> list:
    """Get list of available language codes.

    Returns:
        List of ISO 639-1 language codes.
    """
    return list(TRANSLATIONS.keys())
