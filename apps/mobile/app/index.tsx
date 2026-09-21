import { Text, View } from "react-native";

/**
 * UniServe — Home Screen Placeholder
 *
 * This screen will be developed in Phase 2+ when authentication
 * and role-based access are implemented.
 */
export default function HomeScreen() {
  return (
    <View
      style={{
        flex: 1,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: "#fff",
      }}
    >
      <Text style={{ fontSize: 24, fontWeight: "bold" }}>UniServe</Text>
      <Text style={{ fontSize: 16, marginTop: 8, color: "#666" }}>
        University Cafeteria Platform
      </Text>
    </View>
  );
}
