/* Visite Musées frontend i18n — UI dictionaries in frontend/translations/*.json. */
const supported = ['fr', 'en', 'es'];
const dictionaries = Object.create(null);
let loading = null;
export const supportedLanguages = Object.freeze([...supported]);
export function normalizeLanguage(value) {
  const lang = String(value || 'fr').trim().replace('_','-').split('-')[0].toLowerCase();
  return supported.includes(lang) ? lang : 'fr';
}
export async function loadTranslations(version = '') {
  if (dictionaries.fr) return;
  if (!loading) {
    loading = (async () => {
      // Fetch all language packs once. Translation selection remains synchronous.
      const entries = await Promise.all(supported.map(async language => {
        const url = new URL(`./translations/${language}.json`, import.meta.url);
        if (version) url.searchParams.set('v', version);
        const response = await fetch(url, {cache:'no-cache'});
        if (!response.ok) throw new Error(`Translation ${language}: HTTP ${response.status}`);
        const data = await response.json();
        if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error(`Invalid ${language} translations`);
        return [language, data];
      }));
      for (const [language, data] of entries) dictionaries[language] = data;
    })().catch(error => { loading = null; throw error; });
  }
  return loading;
}
export function translate(key, language = 'fr') {
  const lang = normalizeLanguage(language);
  return dictionaries[lang]?.[key] ?? dictionaries.fr?.[key] ?? key;
}
export function localeTag(language = 'fr') {
  return {fr:'fr-FR',en:'en-GB',es:'es-ES'}[normalizeLanguage(language)];
}
