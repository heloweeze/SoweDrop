from __future__ import annotations

import json
import posixpath
import uuid
from dataclasses import dataclass
from pathlib import Path

import paramiko


class SftpStorageError(Exception):
    """Erreur liée au stockage SFTP."""


@dataclass
class SftpConfig:
    host: str
    port: int
    username: str
    password: str
    remote_base: str = "/commun"


def is_sftp_resource(resource: str | None) -> bool:
    """Indique si une ressource stockée en base correspond à un fichier SFTP."""
    return bool(resource and str(resource).startswith("sftp:"))


class SftpStorage:
    """
    Gestion simple du stockage distant SFTP.

    Le fichier de configuration attendu est :
    data/private/sftp_config.json
    """

    def __init__(self, config: SftpConfig):
        self.config = config

    @classmethod
    def from_project(cls, project_root: str | Path) -> "SftpStorage":
        project_root = Path(project_root)
        config_path = project_root / "data" / "private" / "sftp_config.json"

        if not config_path.exists():
            raise SftpStorageError(
                "Configuration SFTP introuvable. Crée le fichier : "
                f"{config_path}"
            )

        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SftpStorageError(
                f"Le fichier de configuration SFTP est invalide : {exc}"
            ) from exc

        required_keys = ["host", "username", "password"]
        missing = [key for key in required_keys if not data.get(key)]
        if missing:
            raise SftpStorageError(
                "Configuration SFTP incomplète. Clé(s) manquante(s) : "
                + ", ".join(missing)
            )

        return cls(
            SftpConfig(
                host=str(data["host"]),
                port=int(data.get("port", 22)),
                username=str(data["username"]),
                password=str(data["password"]),
                remote_base=str(data.get("remote_base", "/commun")),
            )
        )

    def _connect(self):
        """Ouvre une connexion SFTP et retourne transport + client SFTP."""
        try:
            transport = paramiko.Transport((self.config.host, self.config.port))
            transport.connect(
                username=self.config.username,
                password=self.config.password,
            )
            sftp = paramiko.SFTPClient.from_transport(transport)
            return transport, sftp
        except Exception as exc:
            raise SftpStorageError(f"Connexion SFTP impossible : {exc}") from exc

    def _ensure_remote_dir(self, sftp: paramiko.SFTPClient, remote_dir: str) -> None:
        """Crée le dossier distant s'il n'existe pas déjà."""
        parts = [part for part in remote_dir.split("/") if part]
        current = ""

        for part in parts:
            current = current + "/" + part
            try:
                sftp.stat(current)
            except FileNotFoundError:
                sftp.mkdir(current)

    def upload_file(self, source_file: str | Path) -> str:
        """
        Envoie un fichier local sur le serveur SFTP.

        Retourne une ressource stockable en base, par exemple :
        sftp:/commun/abc12345_document.pdf
        """
        source = Path(source_file)

        if not source.exists():
            raise SftpStorageError(f"Fichier source introuvable : {source}")

        safe_name = source.name.replace(" ", "_")
        remote_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
        remote_dir = self.config.remote_base.rstrip("/") or "/commun"
        remote_path = posixpath.join(remote_dir, remote_name)

        transport, sftp = self._connect()

        try:
            self._ensure_remote_dir(sftp, remote_dir)
            sftp.put(str(source), remote_path)
            return f"sftp:{remote_path}"
        except Exception as exc:
            raise SftpStorageError(f"Upload SFTP impossible : {exc}") from exc
        finally:
            sftp.close()
            transport.close()

    def download_file(self, remote_resource: str, destination_file: str | Path) -> Path:
        """Télécharge un fichier SFTP vers un chemin local."""
        if not is_sftp_resource(remote_resource):
            raise SftpStorageError("La ressource demandée n'est pas une ressource SFTP.")

        remote_path = remote_resource.replace("sftp:", "", 1)
        destination = Path(destination_file)
        destination.parent.mkdir(parents=True, exist_ok=True)

        transport, sftp = self._connect()

        try:
            sftp.get(remote_path, str(destination))
            return destination
        except Exception as exc:
            raise SftpStorageError(f"Téléchargement SFTP impossible : {exc}") from exc
        finally:
            sftp.close()
            transport.close()

    def delete_file(self, remote_resource: str) -> None:
        """Supprime un fichier distant SFTP."""
        if not is_sftp_resource(remote_resource):
            raise SftpStorageError("La ressource demandée n'est pas une ressource SFTP.")

        remote_path = remote_resource.replace("sftp:", "", 1)
        transport, sftp = self._connect()

        try:
            sftp.remove(remote_path)
        except FileNotFoundError:
            return
        except Exception as exc:
            raise SftpStorageError(f"Suppression SFTP impossible : {exc}") from exc
        finally:
            sftp.close()
            transport.close()
