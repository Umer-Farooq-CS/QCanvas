"use client";

// Chart.js bar chart, split into its own module so it can be loaded lazily
// (next/dynamic) instead of shipping chart.js in the /app first-load bundle.
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js";
import { Bar } from "react-chartjs-2";
import type { ChartProps } from "react-chartjs-2";

ChartJS.register(CategoryScale, LinearScale, BarElement, Title, Tooltip, Legend);

export type BarChartProps = Omit<ChartProps<"bar">, "type">;

export default function BarChart(props: BarChartProps) {
  return <Bar {...props} />;
}
