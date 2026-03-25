import { useToastContext } from '@/components/toast-provider'

export function useToast() {
  const { toast } = useToastContext()
  return { toast }
}
