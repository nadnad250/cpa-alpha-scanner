/* ============================================================
   Auth + Credits + Referral — CPA Alpha Scanner
   ============================================================ */

// ---- Génère un code parrainage unique ----
function genRefCode(uid) {
  return 'CPA-' + uid.substring(0, 6).toUpperCase();
}

// ---- Crée un nouveau profil utilisateur dans Firestore ----
async function createUserProfile(user, refCodeUsed) {
  const { db, doc, setDoc, getDoc, updateDoc, increment } = await import('./firebase-config.js');
  const userRef = doc(db, 'users', user.uid);
  const snap = await getDoc(userRef);
  if (snap.exists()) return snap.data();

  const refCode = genRefCode(user.uid);
  const profile = {
    uid:          user.uid,
    email:        user.email,
    name:         user.displayName,
    photo:        user.photoURL,
    credits:      50,            // 50 crédits gratuits à l'inscription
    premiumDays:  0,
    refCode,
    referredBy:   refCodeUsed || null,
    referrals:    0,
    tier:         'free',        // free | silver | gold | premium
    joinedAt:     new Date().toISOString(),
    lastLogin:    new Date().toISOString(),
  };
  await setDoc(userRef, profile);

  // Si parrainage valide → bonus pour les deux
  if (refCodeUsed) {
    await applyReferralBonus(user.uid, refCodeUsed, db, doc, getDoc, updateDoc, increment);
  }
  return profile;
}

// ---- Applique le bonus de parrainage ----
async function applyReferralBonus(newUid, refCode, db, doc, getDoc, updateDoc, increment) {
  try {
    const { collection, query, where, getDocs } = await import('./firebase-config.js');
    const q = query(collection(db, 'users'), where('refCode', '==', refCode));
    const snap = await getDocs(q);
    if (snap.empty) return;
    const referrerDoc = snap.docs[0];
    const referrerRef = doc(db, 'users', referrerDoc.id);
    // Parrain : +30 jours premium + +100 crédits
    await updateDoc(referrerRef, { premiumDays: increment(30), credits: increment(100), referrals: increment(1) });
    // Filleul : +7 jours premium + +50 crédits
    const newUserRef = doc(db, 'users', newUid);
    await updateDoc(newUserRef, { premiumDays: increment(7), credits: increment(50) });
  } catch (e) { console.error('Referral bonus error:', e); }
}

// ---- Connexion Google ----
async function loginWithGoogle(refCode) {
  const { auth, provider, signInWithPopup } = await import('./firebase-config.js');
  const result = await signInWithPopup(auth, provider);
  const profile = await createUserProfile(result.user, refCode);
  localStorage.setItem('cpa_user', JSON.stringify(profile));
  return profile;
}

// ---- Déconnexion ----
async function logout() {
  const { auth, signOut } = await import('./firebase-config.js');
  await signOut(auth);
  localStorage.removeItem('cpa_user');
  window.location.href = 'login.html';
}

// ---- Vérifie auth et redirige si non connecté ----
async function requireAuth() {
  const { auth, onAuthStateChanged, db, doc, getDoc, updateDoc } = await import('./firebase-config.js');
  return new Promise((resolve) => {
    onAuthStateChanged(auth, async (user) => {
      if (!user) { window.location.href = 'login.html'; return; }
      const ref = doc(db, 'users', user.uid);
      const snap = await getDoc(ref);
      if (!snap.exists()) { window.location.href = 'login.html'; return; }
      const profile = snap.data();
      await updateDoc(ref, { lastLogin: new Date().toISOString() });
      localStorage.setItem('cpa_user', JSON.stringify(profile));
      resolve(profile);
    });
  });
}

// ---- Récupère profil depuis localStorage (rapide, pour affichage) ----
function getCachedUser() {
  try { return JSON.parse(localStorage.getItem('cpa_user')); } catch { return null; }
}

// ---- Calcule le tier selon referrals ----
function getTier(referrals) {
  if (referrals >= 25) return { name: 'Gold',   icon: '🥇', color: '#f59e0b' };
  if (referrals >= 10) return { name: 'Silver', icon: '🥈', color: '#94a3b8' };
  if (referrals >= 3)  return { name: 'Bronze', icon: '🥉', color: '#b45309' };
  return { name: 'Free', icon: '🔵', color: '#3b82f6' };
}

export { loginWithGoogle, logout, requireAuth, getCachedUser, getTier, genRefCode };
