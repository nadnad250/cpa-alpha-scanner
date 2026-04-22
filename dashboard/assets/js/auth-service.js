// ============================================================
//  AUTH SERVICE — Firebase Auth + Firestore
//  Toutes les fonctions utilisateur pour login.html, profile.html,
//  referral.html, dashboard.html
// ============================================================

import {
  auth, db, provider,
  signInWithPopup, signInWithEmailAndPassword, createUserWithEmailAndPassword,
  sendPasswordResetEmail, updateProfile, signOut, onAuthStateChanged,
  doc, getDoc, setDoc, updateDoc, increment, arrayUnion,
  collection, query, where, getDocs, orderBy, limit,
  serverTimestamp,
} from './firebase-config.js';

// ---- Génère un code de parrainage unique ----
function genRefCode(uid) {
  return 'CPA-' + uid.substring(0, 6).toUpperCase();
}

// ---- Crée ou récupère le profil utilisateur ----
async function ensureUserProfile(firebaseUser, refCodeUsed) {
  const userRef = doc(db, 'users', firebaseUser.uid);
  const snap = await getDoc(userRef);

  if (snap.exists()) {
    // Profil existant → juste mettre à jour lastLogin
    await updateDoc(userRef, { lastLogin: serverTimestamp() });
    return { ...snap.data(), uid: firebaseUser.uid };
  }

  // ---- Création nouveau profil ----
  const refCode = genRefCode(firebaseUser.uid);
  const profile = {
    uid:            firebaseUser.uid,
    email:          firebaseUser.email,
    name:           firebaseUser.displayName || (firebaseUser.email || '').split('@')[0],
    photo:          firebaseUser.photoURL || null,
    emailVerified:  firebaseUser.emailVerified,
    refCode,
    referredBy:     refCodeUsed || null,
    points:         50 + (refCodeUsed ? 50 : 0),
    premiumDays:    refCodeUsed ? 7 : 0,
    referrals:      0,
    badges:         ['welcome'],
    history:        [
      { date: new Date().toISOString().split('T')[0], action: 'Inscription', points: 50, status: 'credit' }
    ],
    sharedPlatforms: {},
    signalsViewed:  0,
    loginStreak:    1,
    joinedAt:       serverTimestamp(),
    lastLogin:      serverTimestamp(),
  };
  if (refCodeUsed) {
    profile.history.push({ date: new Date().toISOString().split('T')[0], action: 'Bonus parrainage', points: 50, status: 'credit' });
  }
  await setDoc(userRef, profile);

  // ---- Crédite le parrain si refCode valide ----
  if (refCodeUsed) {
    await applyReferralBonus(firebaseUser.uid, refCodeUsed);
  }
  return profile;
}

// ---- Applique le bonus au parrain ----
async function applyReferralBonus(newUid, refCode) {
  try {
    const q = query(collection(db, 'users'), where('refCode', '==', refCode));
    const snap = await getDocs(q);
    if (snap.empty) return;
    const referrerDoc = snap.docs[0];
    const refRef = doc(db, 'users', referrerDoc.id);
    await updateDoc(refRef, {
      referrals:   increment(1),
      points:      increment(100),
      premiumDays: increment(30),
      history:     arrayUnion({
        date: new Date().toISOString().split('T')[0],
        action: 'Nouveau filleul',
        points: 100,
        status: 'credit'
      })
    });
  } catch (e) { console.error('Referral bonus error:', e); }
}

// ---- Connexion Email/Password ----
export async function signInEmail(email, password) {
  const result = await signInWithEmailAndPassword(auth, email, password);
  const profile = await ensureUserProfile(result.user);
  localStorage.setItem('cpa_user', JSON.stringify(profile));
  return profile;
}

// ---- Inscription Email/Password ----
export async function signUpEmail(email, password, name, refCode) {
  const result = await createUserWithEmailAndPassword(auth, email, password);
  if (name) await updateProfile(result.user, { displayName: name });
  const profile = await ensureUserProfile(result.user, refCode);
  if (name) profile.name = name;
  localStorage.setItem('cpa_user', JSON.stringify(profile));
  return profile;
}

// ---- Connexion Google ----
export async function signInGoogle(refCode) {
  const result = await signInWithPopup(auth, provider);
  const profile = await ensureUserProfile(result.user, refCode);
  localStorage.setItem('cpa_user', JSON.stringify(profile));
  return profile;
}

// ---- Reset mot de passe ----
export async function resetPassword(email) {
  await sendPasswordResetEmail(auth, email);
}

// ---- Déconnexion ----
export async function logout() {
  await signOut(auth);
  localStorage.removeItem('cpa_user');
  window.location.href = 'login.html';
}

// ---- Guard : redirige vers login si non connecté ----
export function requireAuth(callback) {
  onAuthStateChanged(auth, async (user) => {
    if (!user) {
      window.location.href = 'login.html';
      return;
    }
    const ref = doc(db, 'users', user.uid);
    const snap = await getDoc(ref);
    if (!snap.exists()) {
      window.location.href = 'login.html';
      return;
    }
    const profile = { ...snap.data(), uid: user.uid };
    localStorage.setItem('cpa_user', JSON.stringify(profile));
    if (callback) callback(profile);
  });
}

// ---- Récupère utilisateur depuis cache (rapide) ----
export function getCachedUser() {
  try { return JSON.parse(localStorage.getItem('cpa_user')); } catch { return null; }
}

// ---- Mise à jour profil utilisateur dans Firestore ----
export async function updateUserData(uid, data) {
  await updateDoc(doc(db, 'users', uid), data);
  // Refresh cache
  const snap = await getDoc(doc(db, 'users', uid));
  if (snap.exists()) {
    localStorage.setItem('cpa_user', JSON.stringify({ ...snap.data(), uid }));
  }
}

// ---- Ajoute points + entrée historique ----
export async function awardPoints(uid, action, points) {
  const histEntry = { date: new Date().toISOString().split('T')[0], action, points, status: 'credit' };
  await updateDoc(doc(db, 'users', uid), {
    points:  increment(points),
    history: arrayUnion(histEntry)
  });
  // Refresh cache
  const snap = await getDoc(doc(db, 'users', uid));
  if (snap.exists()) localStorage.setItem('cpa_user', JSON.stringify({ ...snap.data(), uid }));
}

// ---- Incrémente compteur signaux vus ----
export async function incrementSignalsViewed(uid) {
  await updateDoc(doc(db, 'users', uid), { signalsViewed: increment(1) });
}

// ---- Leaderboard temps réel (top N) ----
export async function fetchLeaderboard(topN = 10) {
  const q = query(collection(db, 'users'), orderBy('points', 'desc'), limit(topN));
  const snap = await getDocs(q);
  return snap.docs.map(d => ({ uid: d.id, ...d.data() }));
}
