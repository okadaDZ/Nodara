import React from 'react';
import { Redirect } from 'expo-router';

/** Legacy route retained so old links open the supported image creation flow. */
export default function LegacyTextCreationRedirect() {
  return <Redirect href="/create/photo" />;
}
