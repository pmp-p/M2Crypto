#!/usr/bin/env python

"""Unit tests for M2Crypto.SMIME.

Copyright (C) 2006 Open Source Applications Foundation. All Rights Reserved.
"""

import unittest
from M2Crypto import SMIME, BIO, Rand, X509

class SMIMETestCase(unittest.TestCase):
    cleartext = 'some text to manipulate'

    def setUp(self):
        # XXX Ugly, but not sure what would be better
        self.signature = self.check_sign()
        self.encrypted = self.check_encrypt()
    
    def check_sign(self):
        buf = BIO.MemoryBuffer(self.cleartext)
        s = SMIME.SMIME()
        s.load_key('signer_key.pem', 'signer.pem')
        p7 = s.sign(buf)
        assert len(buf) == 0
        assert p7.type() == SMIME.PKCS7_SIGNED, p7.type()
        assert isinstance(p7, SMIME.PKCS7), p7
        out = BIO.MemoryBuffer()
        p7.write(out)
        
        buf = out.read()
        
        assert buf[:len('-----BEGIN PKCS7-----')] == '-----BEGIN PKCS7-----'
        buf = buf.strip()
        assert buf[-len('-----END PKCS7-----'):] == '-----END PKCS7-----', buf[-len('-----END PKCS7-----'):]
        assert len(buf) > len('-----END PKCS7-----') + len('-----BEGIN PKCS7-----')
        
        s.write(out, p7, BIO.MemoryBuffer(self.cleartext))
        return out
            
    def check_verify(self):
        s = SMIME.SMIME()
        
        x509 = X509.load_cert('signer.pem')
        sk = X509.X509_Stack()
        sk.push(x509)
        s.set_x509_stack(sk)
        
        st = X509.X509_Store()
        st.load_info('ca.pem')
        s.set_x509_store(st)
        
        p7, data = SMIME.smime_load_pkcs7_bio(self.signature)
        
        assert data.read() == self.cleartext
        assert isinstance(p7, SMIME.PKCS7), p7
        v = s.verify(p7)
        assert v == self.cleartext
    
    def check_verifyBad(self):
        s = SMIME.SMIME()
        
        x509 = X509.load_cert('recipient.pem')
        sk = X509.X509_Stack()
        sk.push(x509)
        s.set_x509_stack(sk)
        
        st = X509.X509_Store()
        st.load_info('recipient.pem')
        s.set_x509_store(st)
        
        p7, data = SMIME.smime_load_pkcs7_bio(self.signature)
        assert data.read() == self.cleartext
        assert isinstance(p7, SMIME.PKCS7), p7
        self.assertRaises(SMIME.PKCS7_Error, s.verify, p7) # Bad signer

    def check_encrypt(self):
        buf = BIO.MemoryBuffer(self.cleartext)
        s = SMIME.SMIME()

        x509 = X509.load_cert('recipient.pem')
        sk = X509.X509_Stack()
        sk.push(x509)
        s.set_x509_stack(sk)

        s.set_cipher(SMIME.Cipher('des_ede3_cbc'))
        p7 = s.encrypt(buf)
        
        assert len(buf) == 0
        assert p7.type() == SMIME.PKCS7_ENVELOPED, p7.type()
        assert isinstance(p7, SMIME.PKCS7), p7
        out = BIO.MemoryBuffer()
        p7.write(out)
    
        buf = out.read()
        
        assert buf[:len('-----BEGIN PKCS7-----')] == '-----BEGIN PKCS7-----'
        buf = buf.strip()
        assert buf[-len('-----END PKCS7-----'):] == '-----END PKCS7-----'
        assert len(buf) > len('-----END PKCS7-----') + len('-----BEGIN PKCS7-----')
        
        s.write(out, p7)
        return out
    
    def check_decrypt(self):
        s = SMIME.SMIME()

        s.load_key('recipient_key.pem', 'recipient.pem')
        
        p7, data = SMIME.smime_load_pkcs7_bio(self.encrypted)
        assert isinstance(p7, SMIME.PKCS7), p7
        self.assertRaises(SMIME.SMIME_Error, s.verify, p7) # No signer
        
        out = s.decrypt(p7)
        assert out == self.cleartext

    def check_decryptBad(self):
        s = SMIME.SMIME()

        s.load_key('signer_key.pem', 'signer.pem')
        
        p7, data = SMIME.smime_load_pkcs7_bio(self.encrypted)
        assert isinstance(p7, SMIME.PKCS7), p7
        self.assertRaises(SMIME.SMIME_Error, s.verify, p7) # No signer

        # Cannot decrypt: no recipient matches certificate
        self.assertRaises(SMIME.PKCS7_Error, s.decrypt, p7)

    def check_signEncryptDecryptVerify(self):
        # sign
        buf = BIO.MemoryBuffer(self.cleartext)
        s = SMIME.SMIME()    
        s.load_key('signer_key.pem', 'signer.pem')
        p7 = s.sign(buf)
        
        # encrypt
        x509 = X509.load_cert('recipient.pem')
        sk = X509.X509_Stack()
        sk.push(x509)
        s.set_x509_stack(sk)
    
        s.set_cipher(SMIME.Cipher('des_ede3_cbc'))
        
        tmp = BIO.MemoryBuffer()
        s.write(tmp, p7, BIO.MemoryBuffer(self.cleartext))

        p7 = s.encrypt(tmp)
        
        signedEncrypted = BIO.MemoryBuffer()
        s.write(signedEncrypted, p7)

        # decrypt
        s = SMIME.SMIME()
    
        s.load_key('recipient_key.pem', 'recipient.pem')
        
        if 1:
            f = open('smime_test.txt', 'wb')
            f.write(signedEncrypted.read())
            f.close()
            p7, data = SMIME.smime_load_pkcs7('smime_test.txt')
            import os
            os.remove('smime_test.txt')
        else:
            # XXX Bug: "not enough data" with straight bio?
            p7, data = SMIME.smime_load_pkcs7_bio(signedEncrypted)
        
        out = s.decrypt(p7)
        
        # verify
        x509 = X509.load_cert('signer.pem')
        sk = X509.X509_Stack()
        sk.push(x509)
        s.set_x509_stack(sk)
        
        st = X509.X509_Store()
        st.load_info('ca.pem')
        s.set_x509_store(st)
        
        p7_bio = BIO.MemoryBuffer(out)
        p7, data = SMIME.smime_load_pkcs7_bio(p7_bio)
        v = s.verify(p7)
        assert v == self.cleartext
    

def suite():
    return unittest.makeSuite(SMIMETestCase, 'check')


if __name__ == '__main__':
    Rand.load_file('randpool.dat', -1)
    unittest.TextTestRunner().run(suite())
    Rand.save_file('randpool.dat')

