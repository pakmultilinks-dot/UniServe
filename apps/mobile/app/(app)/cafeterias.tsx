/**
 * UniServe — Cafeterias Screen
 *
 * Grid of available cafeterias with active status.
 */
import React, { useState, useEffect, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  RefreshControl,
} from "react-native";

import { useTheme } from "../../src/contexts/ThemeContext";
import { Card, Spinner, EmptyState } from "../../src/components/ui";
import { textColor, bgColor, borderColor, colors } from "../../src/theme";
import { getCafeterias, type Cafeteria } from "../../src/services/data";

export default function CafeteriasScreen() {
  const { resolvedTheme } = useTheme();
  const [cafeterias, setCafeterias] = useState<Cafeteria[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const tc = (variant: "primary" | "secondary" | "muted") => textColor(resolvedTheme, variant);
  const bg = (variant: "primary" | "secondary" | "tertiary") => bgColor(resolvedTheme, variant);
  const bc = (variant: "default" | "subtle") => borderColor(resolvedTheme, variant);

  const loadData = useCallback(async () => {
    try {
      const data = await getCafeterias();
      setCafeterias(data);
    } catch {
      // Silent fail
    }
  }, []);

  useEffect(() => {
    loadData().finally(() => setIsLoading(false));
  }, [loadData]);

  const onRefresh = useCallback(async () => {
    setIsRefreshing(true);
    await loadData();
    setIsRefreshing(false);
  }, [loadData]);

  if (isLoading) {
    return (
      <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
        <Spinner label="Loading cafeterias..." />
      </View>
    );
  }

  // Chunk cafeterias into rows of 2
  const rows: Cafeteria[][] = [];
  for (let i = 0; i < cafeterias.length; i += 2) {
    rows.push(cafeterias.slice(i, i + 2));
  }

  return (
    <View style={[styles.screen, { backgroundColor: bg("secondary") }]}>
      <ScrollView
        contentContainerStyle={styles.list}
        refreshControl={<RefreshControl refreshing={isRefreshing} onRefresh={onRefresh} colors={[colors.brand[700]]} />}
      >
        {cafeterias.length === 0 ? (
          <EmptyState emoji="🍽️" title="No cafeterias" description="Available cafeterias will appear here" />
        ) : (
          rows.map((row, rowIdx) => (
            <View key={rowIdx} style={styles.row}>
              {row.map((item) => (
                <Card key={item.id} style={{ flex: 1, backgroundColor: bg("primary"), borderColor: bc("default") }}>
                  <View style={styles.cafeHeader}>
                    <Text style={[styles.cafeName, { color: tc("primary") }]} numberOfLines={1}>
                      {item.name}
                    </Text>
                    <View style={[styles.statusDot, { backgroundColor: item.is_active ? colors.success : colors.neutral[400] }]} />
                  </View>
                  <Text style={{ color: tc("muted"), fontSize: 12, marginTop: 4 }} numberOfLines={2}>
                    {item.location}
                  </Text>
                  <Text style={{ color: tc("secondary"), fontSize: 11, marginTop: 6, fontWeight: "500" }}>
                    {item.is_active ? "Open" : "Closed"}
                  </Text>
                </Card>
              ))}
              {row.length === 1 && <View style={{ flex: 1 }} />}
            </View>
          ))
        )}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: {
    flex: 1,
  },
  list: {
    padding: 16,
    paddingBottom: 32,
  },
  row: {
    gap: 12,
    marginBottom: 12,
  },
  cafeCard: {
    // flex: 1 applied inline
  },
  cafeHeader: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  cafeName: {
    fontSize: 15,
    fontWeight: "600",
    flex: 1,
    marginRight: 8,
  },
  statusDot: {
    width: 8,
    height: 8,
    borderRadius: 4,
  },
});
