// ============================================================
//  FIREBASE CONFIG — CPA Alpha Scanner
//  1. Créer un projet sur https://console.firebase.google.com
//  2. Activer Authentication → Google Sign-In
//  3. Activer Firestore Database
//  4. Remplacer les valeurs ci-dessous par celles de votre projet
// ============================================================

const FIREBASE_CONFIG = {
  apiKey:            "VOTRE_API_KEY",
  authDomain:        "votre-projet.firebaseapp.com",
  projectId:         "votre-projet-id",
  storageBucket:     "votre-projet.appspot.com",
  messagingSenderId: "VOTRE_SENDER_ID",
  appId:             "VOTRE_APP_ID"
};

// ---- Initialisation ----
import { initializeApp }              from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged }
                                      from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";
import { getFirestore, doc, getDoc, setDoc, updateDoc, increment, collection, query, where, getDocs }
                                      from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const app  = initializeApp(FIREBASE_CONFIG);
const auth = getAuth(app);
const db   = getFirestore(app);
const provider = new GoogleAuthProvider();

export { auth, db, provider, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged,
         doc, getDoc, setDoc, updateDoc, increment, collection, query, where, getDocs };
