import { Stack, useRouter } from 'expo-router';
import { StatusBar } from 'expo-status-bar';
import { StyleSheet, Text, TouchableOpacity } from 'react-native';
import { ChevronLeft } from 'lucide-react-native';

function WorkflowReturnButton({ tintColor = '#29262D' }: { tintColor?: string }) {
  const router = useRouter();
  const handlePress = () => {
    if (router.canGoBack()) router.back();
    else router.replace('/');
  };

  return (
    <TouchableOpacity
      activeOpacity={0.62}
      style={styles.returnButton}
      hitSlop={{ top: 10, bottom: 10, left: 8, right: 10 }}
      onPress={handlePress}
      accessibilityRole="button"
      accessibilityLabel="Return to workflows"
    >
      <ChevronLeft size={25} strokeWidth={2.2} color={tintColor} />
      <Text style={[styles.returnLabel, { color: tintColor }]}>Workflows</Text>
    </TouchableOpacity>
  );
}

export default function RootLayout() {
  return (
    <>
      <StatusBar style="light" />
      <Stack
        screenOptions={{
          headerStyle: {
            backgroundColor: '#0F172A',
          },
          headerTintColor: '#F8FAFC',
          headerTitleStyle: {
            fontWeight: '700',
            fontSize: 18,
          },
          contentStyle: {
            backgroundColor: '#0F172A',
          },
          headerShadowVisible: false,
        }}
      >
        <Stack.Screen
          name="index"
          options={{
            title: 'Nodara',
            headerShown: false,
          }}
        />
        <Stack.Screen
          name="how-it-works"
          options={{
            title: 'How it works',
            headerStyle: { backgroundColor: '#F7F5F2' },
            headerTintColor: '#29262D',
          }}
        />
        <Stack.Screen
          name="create/index"
          options={{
            title: 'Create Workflow',
          }}
        />
        <Stack.Screen
          name="create/photo"
          options={{
            title: 'Scan a workflow',
            headerStyle: { backgroundColor: '#F7F5F2' },
            headerTintColor: '#29262D',
          }}
        />
        <Stack.Screen
          name="workflow/[id]"
          options={{
            title: 'Workflow',
            headerStyle: { backgroundColor: '#F7F5F2' },
            headerTintColor: '#29262D',
            headerLeft: ({ tintColor }) => <WorkflowReturnButton tintColor={tintColor} />,
          }}
        />
        <Stack.Screen
          name="agent/[id]"
          options={{
            title: 'Edit Agent',
            headerStyle: { backgroundColor: '#F7F5F2' },
            headerTintColor: '#29262D',
          }}
        />
        <Stack.Screen
          name="settings"
          options={{
            title: 'Settings',
            headerStyle: { backgroundColor: '#F7F5F2' },
            headerTintColor: '#29262D',
          }}
        />
        <Stack.Screen
          name="run/[id]"
          options={{
            title: 'Run Workflow',
            headerStyle: { backgroundColor: '#F7F5F2' },
            headerTintColor: '#29262D',
          }}
        />
        <Stack.Screen
          name="schedule/[id]"
          options={{
            title: 'Schedule',
            headerStyle: { backgroundColor: '#F7F5F2' },
            headerTintColor: '#29262D',
          }}
        />
      </Stack>
    </>
  );
}

const styles = StyleSheet.create({
  returnButton: {
    minHeight: 44,
    flexDirection: 'row',
    alignItems: 'center',
    marginLeft: -8,
    paddingRight: 8,
  },
  returnLabel: {
    fontSize: 16,
    fontWeight: '500',
    marginLeft: -2,
  },
});
