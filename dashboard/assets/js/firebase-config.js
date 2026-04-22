// ============================================================
//  FIREBASE CONFIG — CPA Alpha Scanner
//  Projet : cpa-alpha-scanner
// ============================================================

import { initializeApp } from "https://www.gstatic.com/firebasejs/10.12.0/firebase-app.js";
import {
  getAuth,
  GoogleAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  updateProfile,
  signOut,
  onAuthStateChanged,
} from "https://www.gstatic.com/firebasejs/10.12.0/firebase-auth.js";
import {
  getFirestore,
  doc, getDoc, setDoc, updateDoc, increment,
  collection, query, where, getDocs, orderBy, limit, arrayUnion,
  serverTimestamp,
} from "https://www.gstatic.com/firebasejs/10.12.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey:            "AIzaSyB33-yGJ-lUouAmIjzPJtemnJ_iihdTLeo",
  authDomain:        "cpa-alpha-scanner.firebaseapp.com",
  projectId:         "cpa-alpha-scanner",
  storageBucket:     "cpa-alpha-scanner.firebasestorage.app",
  messagingSenderId: "1069312116229",
  appId:             "1:1069312116229:web:30d8046f18164eb7053e6c",
  measurementId:     "G-WQR5PKH001",
};

const app      = initializeApp(firebaseConfig);
const auth     = getAuth(app);
const db       = getFirestore(app);
const provider = new GoogleAuthProvider();

export {
  app, auth, db, provider,
  GoogleAuthProvider, signInWithPopup, signInWithEmailAndPassword,
  createUserWithEmailAndPassword, sendPasswordResetEmail, updateProfile,
  signOut, onAuthStateChanged,
  doc, getDoc, setDoc, updateDoc, increment,
  collection, query, where, getDocs, orderBy, limit, arrayUnion,
  serverTimestamp,
};
