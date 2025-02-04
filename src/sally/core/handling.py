# -*- encoding: utf-8 -*-
"""
SALLY
sally.core.handling module

EXN Message handling
"""
import datetime
import json
from base64 import urlsafe_b64encode as encodeB64
from collections import namedtuple
from urllib import parse

from hio.base import doing
from hio.core import http
from hio.help import decking, Hict
from keri import help, kering
from keri.core import coring
from keri.end import ending
from keri.help import helping

from sally.core import httping

logger = help.ogler.getLogger()
QVI_SCHEMA = "EBfdlu8R27Fbx-ehrqwImnK-8Cm79sqbAQ4MmvEAYqao"
LE_SCHEMA = "ENPXp1vQzRF6JwIuS-mp2U8Uf1MoADoP_GqQ62VsDZWY"
OOR_AUTH_SCHEMA = "EKA57bKBKxr_kN7iN5i7lMUxpMG-s19dRcmov1iDxz-E"
OOR_SCHEMA = "EBNaNu-M9P5cgrnfl2Fvymy4E_jvxxyjb70PRtiANlJy"
IDCARD_SCHEMA = "EEYMNgyQNHWrsO4m65Px84M93o2url6aUpTFqNdMZdKt"


def loadHandlers(cdb, exc):
    """ Load handlers for the peer-to-peer challenge response protocol

    Parameters:
        cdb (CueBaser): communication escrow database environment
        exc (Exchanger): Peer-to-peer message router

    """
    proofs = PresentationProofHandler(cdb=cdb)
    exc.addHandler(proofs)


class PresentationProofHandler(doing.Doer):
    """ Processor for responding to presentation proof peer to peer message.

      The payload of the message is expected to have the following format:

    """

    resource = "/presentation"

    def __init__(self, cdb, cues=None, **kwa):
        """ Initialize instance

        Parameters:
            cdb (CueBaser): communication escrow database environment
            cue(Deck): outbound cues
            **kwa (dict): keyword arguments passes to super Doer

        """
        self.msgs = decking.Deck()
        self.cues = cues if cues is not None else decking.Deck()
        self.cdb = cdb

        super(PresentationProofHandler, self).__init__()

    def do(self, tymth, tock=0.0, **opts):
        """ Handle incoming messages by queueing presentation messages to be handled when credential is received

        Parameters:
            tymth (function): injected function wrapper closure returned by .tymen() of
                Tymist instance. Calling tymth() returns associated Tymist .tyme.
            tock (float): injected initial tock value

        Messages:
            payload is dict representing the body of a /presentation message
            pre is qb64 identifier prefix of sender


        """
        self.wind(tymth)
        self.tock = tock
        yield self.tock

        while True:
            while self.msgs:
                msg = self.msgs.popleft()
                payload = msg["payload"]
                # TODO: limit presentations from issuee or issuer from flag.

                sender = payload["i"]
                said = payload["a"] if "a" in payload else payload["n"]

                prefixer = coring.Prefixer(qb64=sender)
                saider = coring.Saider(qb64=said)
                now = coring.Dater()

                self.cdb.snd.pin(keys=(saider.qb64,), val=prefixer)
                self.cdb.iss.pin(keys=(saider.qb64,), val=now)

                yield self.tock

            yield self.tock


IDCARD_TYPE = 'IdCard'


class Communicator(doing.DoDoer):
    """
    Communicator is responsible for communicating the receipt and successful verification
    of credential presentation and revocation messages from external third parties via
    web hook API calls.


    """

    def __init__(self, hby, hab, cdb, reger, auth, hook, timeout=10, retry=3.0):
        """

        Create a communicator capable of persistent processing of messages and performing
        web hook calls.

        Parameters:
            hby (Habery): identifier database environment
            hab (Hab): identifier environment of this Communicator.  Used to sign hook calls
            cdb (CueBaser): communication escrow database environment
            reger (Reger): credential registry and database
            auth (str): AID of external authority for contacts and credentials
            hook (str): web hook to call in response to presentations and revocations
            timeout (int): escrow timeout (in minutes) for events not delivered to upstream web hook
            retry (float): retry delay (in seconds) for failed web hook attempts

        """
        self.hby = hby
        self.hab = hab
        self.cdb = cdb
        self.reger = reger
        self.hook = hook
        self.auth = auth
        self.timeout = timeout
        self.retry = retry
        self.clients = dict()

        super(Communicator, self).__init__(doers=[doing.doify(self.escrowDo)])

    def processPresentations(self):

        for (said,), dater in self.cdb.iss.getItemIter():
            # cancel presentations that have been around longer than timeout
            now = helping.nowUTC()
            print(f"looking for credential {said}")
            if now - dater.datetime > datetime.timedelta(minutes=self.timeout):
                self.cdb.iss.rem(keys=(said,))
                continue

            if self.reger.saved.get(keys=(said,)) is not None:
                creder = self.reger.creds.get(keys=(said,))
                try:
                    regk = creder.status
                    state = self.reger.tevers[regk].vcState(creder.said)
                    if state is None or state.ked['et'] not in (coring.Ilks.iss, coring.Ilks.bis):
                        raise kering.InvalidCredentialStateError(f"Revoked credential {creder.said} being presented")

                    if creder.schema == IDCARD_SCHEMA:
                        self.validateIdCard(creder)
                    else:
                        raise kering.ValidationError(f"credential {creder.said} is of unsupported schema"
                                                     f" {creder.schema} from issuer {creder.issuer}")

                except kering.InvalidCredentialStateError as ex:
                    print(ex)
                    logger.error(f'Revoked credential {creder.said} from issuer {creder.issuer} being presented.')
                except kering.ValidationError as ex:
                    print(ex)
                    logger.error(f"credential {creder.said} from issuer {creder.issuer} failed validation: {ex}")
                else:
                    self.cdb.recv.pin(keys=(said, dater.qb64), val=creder)
                finally:
                    self.cdb.iss.rem(keys=(said,))


    def processRevocations(self):

        for (said,), dater in self.cdb.rev.getItemIter():

            # cancel revocations that have been around longer than timeout
            now = helping.nowUTC()
            if now - dater.datetime > datetime.timedelta(minutes=self.timeout):
                self.cdb.rev.rem(keys=(said,))
                continue

            creder = self.reger.creds.get(keys=(said,))
            if creder is None:  # received revocation before credential.  probably an error but let it timeout
                continue

            regk = creder.status
            state = self.reger.tevers[regk].vcState(creder.said)
            if state is None:  # received revocation before status.  probably an error but let it timeout
                continue

            elif state.ked['et'] in (coring.Ilks.iss, coring.Ilks.bis):  # haven't received revocation event yet
                continue

            elif state.ked['et'] in (coring.Ilks.rev, coring.Ilks.brv):  # revoked
                self.cdb.rev.rem(keys=(said,))
                self.cdb.revk.pin(keys=(said, dater.qb64), val=creder)

    def processReceived(self, db, action):

        for (said, dates), creder in db.getItemIter():
            # if said not in self.clients:
            resource = creder.schema
            actor = creder.issuer
            if action == "iss":  # presentation of issued credential
                if creder.schema == IDCARD_SCHEMA:
                    data = self.idCardPayload(creder)
                    print(f"credential {creder.said} is of schema {creder.schema} from issuer {creder.issuer}")
                else:
                    raise kering.ValidationError(f"credential {creder.said} is of unsupported schema"
                                                    f" {creder.schema} from issuer {creder.issuer}")
            else:  # revocation of credential
                data = self.revokePayload(creder)

            self.request(creder.said, resource, action, actor, data)
                # continue


            db.rem(keys=(said, dates))
            self.cdb.ack.pin(keys=(said,), val=creder)



            # (client, clientDoer) = self.clients[said]
            # if client.responses:
            #     response = client.responses.popleft()
            #     self.remove([clientDoer])
            #     client.close()
            #     del self.clients[said]

            #     if 200 <= response["status"] < 300:
            #         db.rem(keys=(said, dates))
            #         self.cdb.ack.pin(keys=(said,), val=creder)
            #     else:
            #         dater = coring.Dater(qb64=dates)
            #         now = helping.nowUTC()
            #         if now - dater.datetime > datetime.timedelta(minutes=self.timeout):
            #             db.rem(keys=(said, dates))

    def processAcks(self):
        for (said,), creder in self.cdb.ack.getItemIter():
            # TODO: generate EXN ack message with credential information
            # print(f"ACK for credential {said} will be sent to {creder.issuer}")
            self.cdb.ack.rem(keys=(said,))

    def escrowDo(self, tymth, tock=1.0):
        """ Process escrows of comms pipeline

        Steps involve:
           1. Sending local event with sig to other participants
           2. Waiting for signature threshold to be met.
           3. If elected and delegated identifier, send complete event to delegator
           4. If delegated, wait for delegator's anchor
           5. If elected, send event to witnesses and collect receipts.
           6. Otherwise, wait for fully receipted event

        Parameters:
            tymth (function): injected function wrapper closure returned by .tymen() of
                Tymist instance. Calling tymth() returns associated Tymist .tyme.
            tock (float): injected initial tock value.  Default to 1.0 to slow down processing

        """
        # enter context
        self.wind(tymth)
        self.tock = tock
        _ = (yield self.tock)

        while True:
            try:
                self.processEscrows()
            except Exception as e:
                print(e)

            yield self.retry

    def processEscrows(self):
        """
        Process communication pipelines

        """
        self.processPresentations()
        self.processRevocations()
        self.processReceived(db=self.cdb.recv, action="iss")
        self.processReceived(db=self.cdb.revk, action="rev")
        self.processAcks()

    def request(self, said, resource, action, actor, data):
        """ Generate and launch request to remote hook

        Parameters:
            said (str): qb64 SAID of credential
            data (dict): serializable body to send with call
            action (str): the action performed on he resource [iss|rev]
            actor (str): qualified b64 AID of sender of the event
            resource (str): the resource type that triggered the event

        """

        raw = json.dumps(data).encode("utf-8")
        print(f"Valid credential {raw}")

        return
        purl = parse.urlparse(self.hook)
        client = http.clienting.Client(hostname=purl.hostname, port=purl.port)
        clientDoer = http.clienting.ClientDoer(client=client)
        self.extend([clientDoer])

        body = dict(
            action=action,
            actor=actor,
            data=data
        )

        raw = json.dumps(body).encode("utf-8")
        headers = Hict([
            ("Content-Type", "application/json"),
            ("Content-Length", len(raw)),
            ("Connection", "close"),
            ("Sally-Resource", resource),
            ("Sally-Timestamp", helping.nowIso8601()),
        ])
        path = purl.path or "/"

        keyid = encodeB64(self.hab.kever.serder.verfers[0].raw).decode('utf-8')
        header, unq = httping.siginput(self.hab, "sig0", "POST", path, headers, fields=["Sally-Resource", "@method",
                                                                                        "@path",
                                                                                        "Sally-Timestamp"],
                                       alg="ed25519", keyid=keyid)

        headers.extend(header)
        signage = ending.Signage(markers=dict(sig0=unq), indexed=True, signer=self.hab.pre, ordinal=None, digest=None,
                                 kind=None)

        headers.extend(ending.signature([signage]))

        client.request(
            method='POST',
            path=path,
            qargs=parse.parse_qs(purl.query),
            headers=headers,
            body=raw
        )

        self.clients[said] = (client, clientDoer)

    def validateIdCard(self, creder):
        card_id_said = IDCARD_SCHEMA
        if creder.schema != card_id_said:
            raise kering.ValidationError(f'Invalid schema SAID {creder.schema} for {IDCARD_TYPE} '
                                         f'credential SAID: {card_id_said}')
        if not creder.issuer == self.auth:
            raise kering.ValidationError("CardId credential not issued by known valid issuer")

        print(f"Validated {IDCARD_TYPE} credential {creder.said} from issuer {creder.issuer}")

    @staticmethod
    def idCardPayload(creder):
        a = creder.crd["a"]
        data = dict(
            schema=creder.schema,
            issuer=creder.issuer,
            issueTimestamp=a["dt"],
            credential=creder.said,
            recipient=a["i"],
            firstName=a["firstName"],
            lastName=a["lastName"],
            birthDate=a["birthDate"],
            height=a["height"],
            sex=a["sex"],
            origin=a["origin"],
            authority=a["authority"],
            expiry=a["expiry"]
        )

        return data


    def revokePayload(self, creder):
        regk = creder.status
        state = self.reger.tevers[regk].vcState(creder.said)

        data = dict(
            schema=creder.schema,
            credential=creder.said,
            revocationTimestamp=state.ked["dt"]
        )

        return data
