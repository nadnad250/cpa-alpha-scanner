/* ==================================================
   POINTS & BADGES SYSTEM — CPA Alpha Scanner
   ================================================== */

// ---- Actions qui donnent des points ----
export const POINT_ACTIONS = {
  SIGNUP:            { points: 50,  label: 'Inscription',                    icon: '🎉' },
  REFERRAL_SUCCESS:  { points: 100, label: 'Parrainage réussi',              icon: '🤝' },
  DAILY_LOGIN:       { points: 5,   label: 'Connexion quotidienne',          icon: '📅' },
  STREAK_7:          { points: 25,  label: 'Série 7 jours',                  icon: '🔥' },
  STREAK_30:         { points: 100, label: 'Série 30 jours',                 icon: '🏆' },
  FIRST_SIGNAL:      { points: 10,  label: '1er signal visualisé',           icon: '👁' },
  SHARE_TELEGRAM:    { points: 20,  label: 'Partage Telegram',               icon: '✈' },
  SHARE_WHATSAPP:    { points: 20,  label: 'Partage WhatsApp',               icon: '💬' },
  SHARE_TWITTER:     { points: 20,  label: 'Partage Twitter/X',              icon: '🐦' },
  PROFILE_COMPLETE:  { points: 30,  label: 'Profil complété',                icon: '✅' },
  EMAIL_VERIFIED:    { points: 25,  label: 'Email vérifié',                  icon: '📧' },
  TELEGRAM_LINKED:   { points: 50,  label: 'Telegram relié',                 icon: '🔗' },
};

// ---- Paliers de récompenses (convertir points → Premium) ----
export const POINT_MILESTONES = [
  { points: 100,   reward: '+7 jours Premium',         days: 7,   icon: '🎁' },
  { points: 300,   reward: '+1 mois Premium',          days: 30,  icon: '⭐' },
  { points: 750,   reward: '+3 mois Premium',          days: 90,  icon: '💎' },
  { points: 2000,  reward: '+1 an Premium',            days: 365, icon: '👑' },
  { points: 5000,  reward: 'Premium À VIE',            days: 999999, icon: '🏆' },
];

// ---- Tiers basés sur parrainages actifs ----
export const TIERS = [
  { id: 'free',    name: 'Free',    minRefs: 0,  icon: '🔵', color: '#3b82f6', perks: ['3 signaux/jour', 'Dashboard de base'] },
  { id: 'bronze',  name: 'Bronze',  minRefs: 3,  icon: '🥉', color: '#b45309', perks: ['Signaux illimités', 'Historique 30j'] },
  { id: 'silver',  name: 'Silver',  minRefs: 10, icon: '🥈', color: '#94a3b8', perks: ['+ Alertes Telegram', 'Historique 90j'] },
  { id: 'gold',    name: 'Gold',    minRefs: 25, icon: '🥇', color: '#f59e0b', perks: ['+ Rapport hebdo privé', 'Accès beta'] },
  { id: 'diamond', name: 'Diamond', minRefs: 50, icon: '💎', color: '#06b6d4', perks: ['+ Appels 1-à-1 mensuel', 'Accès VIP'] },
];

// ---- Collection de badges ----
export const BADGES = [
  { id: 'welcome',      name: 'Bienvenue',         icon: '🎉', desc: 'Compte créé',                                rarity: 'common' },
  { id: 'first_view',   name: 'Premier Regard',    icon: '👁',  desc: 'Premier signal consulté',                    rarity: 'common' },
  { id: 'email_verif',  name: 'Vérifié',           icon: '✅', desc: 'Email confirmé',                             rarity: 'common' },
  { id: 'telegram_lnk', name: 'Connecté',          icon: '🔗', desc: 'Telegram relié',                             rarity: 'common' },
  { id: 'first_share',  name: 'Premier Partage',   icon: '📢', desc: 'Lien partagé pour la première fois',         rarity: 'common' },
  { id: 'first_ref',    name: 'Ambassadeur',       icon: '🤝', desc: 'Premier filleul inscrit',                    rarity: 'uncommon' },
  { id: 'streak_7',     name: 'Assidu',            icon: '🔥', desc: '7 jours consécutifs de connexion',           rarity: 'uncommon' },
  { id: 'streak_30',    name: 'Inarrêtable',       icon: '⚡', desc: '30 jours consécutifs de connexion',          rarity: 'rare' },
  { id: 'bronze',       name: 'Bronze',            icon: '🥉', desc: '3 parrainages réussis',                      rarity: 'uncommon' },
  { id: 'silver',       name: 'Silver',            icon: '🥈', desc: '10 parrainages réussis',                     rarity: 'rare' },
  { id: 'gold',         name: 'Gold',              icon: '🥇', desc: '25 parrainages réussis',                     rarity: 'epic' },
  { id: 'diamond',      name: 'Diamond',           icon: '💎', desc: '50 parrainages réussis',                     rarity: 'legendary' },
  { id: 'premium',      name: 'Membre Premium',    icon: '⭐', desc: 'Abonnement Premium actif',                   rarity: 'rare' },
  { id: 'lifetime',     name: 'À Vie',             icon: '👑', desc: 'Abonnement Premium à vie',                   rarity: 'legendary' },
  { id: 'early_bird',   name: 'Pionnier',          icon: '🚀', desc: 'Parmi les 100 premiers inscrits',            rarity: 'legendary' },
  { id: 'top_10',       name: 'Top 10',            icon: '🏆', desc: 'Top 10 du classement parrainage',            rarity: 'epic' },
  { id: 'sharp',        name: 'Œil Affûté',        icon: '🎯', desc: '100 signaux consultés',                      rarity: 'uncommon' },
  { id: 'veteran',      name: 'Vétéran',           icon: '🎖', desc: '365 jours sur la plateforme',                rarity: 'epic' },
  { id: 'millionnaire', name: 'Millionnaire',      icon: '💰', desc: '5000 points cumulés',                        rarity: 'legendary' },
  { id: 'social',       name: 'Influenceur',       icon: '📱', desc: 'Partage sur 3 plateformes différentes',      rarity: 'uncommon' },
];

// ---- Couleurs par rareté ----
export const RARITY = {
  common:    { color: '#94a3b8', bg: 'rgba(148,163,184,.1)',  border: 'rgba(148,163,184,.3)' },
  uncommon:  { color: '#10b981', bg: 'rgba(16,185,129,.1)',   border: 'rgba(16,185,129,.3)' },
  rare:      { color: '#3b82f6', bg: 'rgba(59,130,246,.1)',   border: 'rgba(59,130,246,.3)' },
  epic:      { color: '#a855f7', bg: 'rgba(168,85,247,.1)',   border: 'rgba(168,85,247,.3)' },
  legendary: { color: '#f59e0b', bg: 'rgba(245,158,11,.1)',   border: 'rgba(245,158,11,.3)' },
};

// ---- Helpers ----
export function getTier(referrals) {
  for (let i = TIERS.length - 1; i >= 0; i--) {
    if (referrals >= TIERS[i].minRefs) return TIERS[i];
  }
  return TIERS[0];
}

export function getNextMilestone(points) {
  return POINT_MILESTONES.find(m => m.points > points);
}

export function getProgressToNext(points) {
  const next = getNextMilestone(points);
  if (!next) return { pct: 100, next: null };
  const prev = POINT_MILESTONES.filter(m => m.points <= points).pop();
  const prevPts = prev ? prev.points : 0;
  const pct = Math.round(((points - prevPts) / (next.points - prevPts)) * 100);
  return { pct, next, prevPts };
}

export function computeBadges(user) {
  const unlocked = new Set(user.badges || []);
  // Auto-unlock selon stats
  if ((user.referrals || 0) >= 1)  unlocked.add('first_ref');
  if ((user.referrals || 0) >= 3)  unlocked.add('bronze');
  if ((user.referrals || 0) >= 10) unlocked.add('silver');
  if ((user.referrals || 0) >= 25) unlocked.add('gold');
  if ((user.referrals || 0) >= 50) unlocked.add('diamond');
  if ((user.points || 0) >= 5000)  unlocked.add('millionnaire');
  if ((user.loginStreak || 0) >= 7)  unlocked.add('streak_7');
  if ((user.loginStreak || 0) >= 30) unlocked.add('streak_30');
  if ((user.signalsViewed || 0) >= 100) unlocked.add('sharp');
  if ((user.daysActive || 0) >= 365) unlocked.add('veteran');
  if (user.emailVerified) unlocked.add('email_verif');
  if (user.telegramLinked) unlocked.add('telegram_lnk');
  if (user.premiumActive) unlocked.add('premium');
  if (user.lifetime) unlocked.add('lifetime');
  if (user.earlyBird) unlocked.add('early_bird');
  return Array.from(unlocked);
}
