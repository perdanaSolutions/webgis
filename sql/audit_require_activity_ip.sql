-- Baris baru di audit.user_activities wajib punya ip_address.
-- Baris lama yang NULL tidak diubah: trigger append-only menolak UPDATE/DELETE.

CREATE OR REPLACE FUNCTION audit.require_activity_ip()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.ip_address IS NULL THEN
        RAISE EXCEPTION 'audit.user_activities.ip_address wajib diisi';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS user_activities_require_ip ON audit.user_activities;

CREATE TRIGGER user_activities_require_ip
    BEFORE INSERT ON audit.user_activities
    FOR EACH ROW
    EXECUTE FUNCTION audit.require_activity_ip();
