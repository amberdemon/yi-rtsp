"""Create a private local CA and renew only its home-network server leaf."""
from __future__ import annotations
import argparse
from datetime import datetime,timedelta,timezone
import ipaddress
import json
import os
from pathlib import Path
import re
import tempfile
from cryptography import x509
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID,ExtendedKeyUsageOID


def _names(hosts):
    result=[]
    for host in sorted(set(hosts)):
        try:address=ipaddress.ip_address(host)
        except ValueError:
            if host!='localhost' and not re.fullmatch(r'[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.local',host):
                raise ValueError('Only localhost and explicit .local names are supported')
            result.append(x509.DNSName(host));continue
        if not address.is_private or address.is_unspecified or address.is_multicast:
            raise ValueError('Only explicit private or loopback addresses are supported')
        result.append(x509.IPAddress(address))
    if not result:raise ValueError('At least one TLS hostname is required')
    return result


def _write(path,data):
    fd,name=tempfile.mkstemp(prefix='.viewer-tls-',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f:f.write(data);f.flush();os.fsync(f.fileno())
        os.chmod(name,0o600);os.replace(name,path)
    finally:
        if os.path.exists(name):os.unlink(name)


def prepare_tls(directory:Path,hosts):
    names=_names(hosts);directory.mkdir(parents=True,exist_ok=True);directory.chmod(0o700)
    key_path=directory/'ca.key';ca_path=directory/'ca.pem';now=datetime.now(timezone.utc)
    if key_path.exists()!=ca_path.exists():raise ValueError('Incomplete viewer CA; restore its matching certificate and key')
    if key_path.exists():
        ca_key=serialization.load_pem_private_key(key_path.read_bytes(),password=None)
        ca=x509.load_pem_x509_certificate(ca_path.read_bytes())
        if ca.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)!=ca_key.public_key().public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo):raise ValueError('Viewer CA key does not match its certificate')
    else:
        ca_key=ec.generate_private_key(ec.SECP256R1())
        subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'YI View Private Home CA')])
        ca=(x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=3650))
            .add_extension(x509.BasicConstraints(ca=True,path_length=0),critical=True)
            .add_extension(x509.KeyUsage(False,False,False,False,False,True,True,False,False),critical=True)
            .sign(ca_key,hashes.SHA256()))
        _write(key_path,ca_key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
        _write(ca_path,ca.public_bytes(serialization.Encoding.PEM))
    _write(directory/'yi-view-home-ca.crt',ca.public_bytes(serialization.Encoding.DER))
    cert_path=directory/'server.pem';server_key_path=directory/'server.key'
    if cert_path.exists() and server_key_path.exists():
        leaf=x509.load_pem_x509_certificate(cert_path.read_bytes())
        if set(leaf.extensions.get_extension_for_class(x509.SubjectAlternativeName).value)==set(names) and leaf.not_valid_after_utc>now+timedelta(days=30):
            return
    key=ec.generate_private_key(ec.SECP256R1())
    subject=x509.Name([x509.NameAttribute(NameOID.COMMON_NAME,'YI View Home Viewer')])
    leaf=(x509.CertificateBuilder().subject_name(subject).issuer_name(ca.subject).public_key(key.public_key())
          .serial_number(x509.random_serial_number()).not_valid_before(now-timedelta(minutes=5)).not_valid_after(now+timedelta(days=365))
          .add_extension(x509.SubjectAlternativeName(names),critical=False)
          .add_extension(x509.BasicConstraints(ca=False,path_length=None),critical=True)
          .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),critical=False)
          .add_extension(x509.KeyUsage(True,False,False,False,False,False,False,False,False),critical=True)
          .sign(ca_key,hashes.SHA256()))
    _write(server_key_path,key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()))
    _write(cert_path,leaf.public_bytes(serialization.Encoding.PEM)+ca.public_bytes(serialization.Encoding.PEM))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--directory',type=Path,default=Path('/data/viewer/tls'))
    parser.add_argument('--network-file',type=Path,default=Path('/data/viewer/network.json'))
    args=parser.parse_args()
    hosts=json.loads(args.network_file.read_text())['hosts'] if args.network_file.exists() else ['localhost','127.0.0.1']
    prepare_tls(args.directory,hosts)
    print('Private viewer HTTPS certificate ready; CA trust remains a user-controlled device step.')
