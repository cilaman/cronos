import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '../api';

// 1. usePlugins — query for all plugin data (installed, available, marketplaces)
export function usePlugins() {
  return useQuery({
    queryKey: ['plugins'],
    queryFn: api.plugins,
  });
}

// 2. useInstallPlugin — install a plugin by id and optional scope
export function useInstallPlugin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ pluginId, scope }: { pluginId: string; scope?: string }) =>
      api.installPlugin(pluginId, scope),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plugins'] });
    },
  });
}

// 3. useUninstallPlugin — uninstall a plugin by id
export function useUninstallPlugin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (pluginId: string) => api.uninstallPlugin(pluginId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plugins'] });
    },
  });
}

// 4. useEnablePlugin — enable a plugin by id
export function useEnablePlugin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (pluginId: string) => api.enablePlugin(pluginId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plugins'] });
    },
  });
}

// 5. useDisablePlugin — disable a plugin by id
export function useDisablePlugin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (pluginId: string) => api.disablePlugin(pluginId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plugins'] });
    },
  });
}

// 6. useAddMarketplace — add a marketplace by source URL
export function useAddMarketplace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (source: string) => api.addMarketplace(source),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plugins'] });
    },
  });
}

// 7. useRemoveMarketplace — remove a marketplace by name
export function useRemoveMarketplace() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => api.removeMarketplace(name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['plugins'] });
    },
  });
}
