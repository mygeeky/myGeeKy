package org.mygeeky.drive

import com.google.android.gms.auth.GoogleAuthUtil
import com.google.android.gms.auth.api.identity.AuthorizationRequest
import com.google.android.gms.auth.api.identity.Identity
import com.google.android.gms.common.api.Scope
import expo.modules.kotlin.Promise
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition

// Asks Google for one thing only: drive.appdata, myGeeKy's own hidden folder in the user's Drive.
// Never add another scope (the privacy policy promises this one only; `drive` is restricted).
private const val SCOPE = "https://www.googleapis.com/auth/drive.appdata"
private const val REQUEST_CODE = 47011

class GoogleDriveAuthModule : Module() {
  private var pending: Promise? = null

  override fun definition() = ModuleDefinition {
    Name("GoogleDriveAuth")

    // interactive: show Google's sheet if the user still has to choose an account or allow access
    AsyncFunction("authorize") { interactive: Boolean, promise: Promise ->
      val activity = appContext.throwingActivity
      val request = AuthorizationRequest.builder().setRequestedScopes(listOf(Scope(SCOPE))).build()
      Identity.getAuthorizationClient(activity).authorize(request)
        .addOnSuccessListener { result ->
          val intent = result.pendingIntent
          if (result.hasResolution() && intent != null) {
            if (!interactive) {
              promise.reject("NEEDS_SIGN_IN", "Google needs you to sign in again", null)
            } else if (pending != null) {
              promise.reject("BUSY", "A Google sign-in is already open", null)
            } else {
              pending = promise
              try {
                activity.startIntentSenderForResult(intent.intentSender, REQUEST_CODE, null, 0, 0, 0)
              } catch (e: Exception) {
                pending = null
                promise.reject("FAILED", e.message ?: "Couldn't open Google's sign-in", e)
              }
            }
          } else {
            val token = result.accessToken
            if (token == null) promise.reject("FAILED", "Google gave no access", null)
            else promise.resolve(mapOf("accessToken" to token))
          }
        }
        .addOnFailureListener { e -> promise.reject("FAILED", e.message ?: "Google's sign-in failed", e) }
    }

    // a token Drive refused (it ended): dropped from Google's cache, so the next authorize gets a new one
    AsyncFunction("clearToken") { token: String ->
      GoogleAuthUtil.clearToken(appContext.reactContext ?: appContext.throwingActivity, token)
    }

    OnActivityResult { activity, payload ->
      if (payload.requestCode != REQUEST_CODE) return@OnActivityResult
      val promise = pending ?: return@OnActivityResult
      pending = null
      try {
        val result = Identity.getAuthorizationClient(activity).getAuthorizationResultFromIntent(payload.data)
        val token = result.accessToken
        if (token == null) promise.reject("FAILED", "Google gave no access", null)
        else promise.resolve(mapOf("accessToken" to token))
      } catch (e: Exception) {
        promise.reject("CANCELLED", "The sign-in was cancelled", e)
      }
    }
  }
}
