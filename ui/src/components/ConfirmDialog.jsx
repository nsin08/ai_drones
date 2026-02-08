import { useUIStore } from '../stores/uiStore';

export default function ConfirmDialog() {
  const confirmDialog = useUIStore((s) => s.confirmDialog);
  const hideConfirm = useUIStore((s) => s.hideConfirm);

  if (!confirmDialog) return null;

  const { title, body, droneIds, onConfirm } = confirmDialog;

  const handleConfirm = () => {
    onConfirm?.();
    hideConfirm();
  };

  return (
    <div className="confirm-overlay" onClick={hideConfirm}>
      <div className="confirm-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="confirm-title">{title || 'Confirm Action'}</div>
        <div className="confirm-body">{body}</div>
        {droneIds?.length > 0 && (
          <div className="confirm-drones">
            <strong>Affected drones:</strong>{' '}
            {droneIds.length > 6
              ? `${droneIds.slice(0, 6).join(', ')} +${droneIds.length - 6} more`
              : droneIds.join(', ')}
          </div>
        )}
        <div className="confirm-actions">
          <button className="confirm-btn confirm-btn--cancel" onClick={hideConfirm}>Cancel</button>
          <button className="confirm-btn confirm-btn--ok" onClick={handleConfirm}>Confirm</button>
        </div>
      </div>
    </div>
  );
}
