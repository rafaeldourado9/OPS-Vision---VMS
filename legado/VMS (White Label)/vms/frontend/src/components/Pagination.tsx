interface PaginationProps {
  currentPage: number
  totalCount: number
  pageSize: number
  onPageChange: (page: number) => void
}

export default function Pagination({ currentPage, totalCount, pageSize, onPageChange }: PaginationProps) {
  const totalPages = Math.ceil(totalCount / pageSize)
  if (totalPages <= 1) return null

  return (
    <div className="flex items-center justify-center gap-2 mt-4">
      <button
        disabled={currentPage <= 1}
        onClick={() => onPageChange(currentPage - 1)}
        className="px-3 py-1.5 rounded-lg bg-vms-card text-sm disabled:opacity-40 hover:bg-vms-card-hover transition-colors"
      >
        Anterior
      </button>
      <span className="text-vms-muted text-sm">
        {currentPage} / {totalPages}
      </span>
      <button
        disabled={currentPage >= totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        className="px-3 py-1.5 rounded-lg bg-vms-card text-sm disabled:opacity-40 hover:bg-vms-card-hover transition-colors"
      >
        Próxima
      </button>
    </div>
  )
}
