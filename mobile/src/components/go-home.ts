// Back to Home after setup or a scan, leaving exactly one Home: whatever was opened on top of it (setup, the
// scanner, or setup on top of an older Home) is closed first. A plain replace('/home') left the Home it was
// opened from underneath, with all its feeds still loaded, and Back then showed that hidden Home.
import { router } from 'expo-router';

export function goHome() {
  if (router.canDismiss()) router.dismissAll();
  router.replace('/home');
}
