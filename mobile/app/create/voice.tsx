import React from 'react';
import { Redirect } from 'expo-router';

/** Voice is reserved for creating or editing an individual agent's instructions. */
export default function LegacyVoiceCreationRedirect() {
  return <Redirect href="/create/photo" />;
}
