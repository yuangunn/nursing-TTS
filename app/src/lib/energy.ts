import { createContext, useContext } from "react";

/** Lets any playing visualizer pump the background scene. */
export const EnergyContext = createContext<(e: number) => void>(() => undefined);
export const useEnergy = () => useContext(EnergyContext);
