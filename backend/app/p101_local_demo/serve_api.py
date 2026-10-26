"""Explicit future loopback-only P101 API launcher; never starts on import."""

import argparse

from app.p101_local_demo.api_reader import validate_api_settings
from app.p101_local_demo.setup_config import load_settings


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',required=True)
    parser.add_argument('--instance',required=True)
    parser.add_argument('--serve',action='store_true')
    args=parser.parse_args(argv)
    try:
        settings=load_settings(args.config)
        validate_api_settings(settings)
        if args.serve is not True or args.instance != settings.instance_uuid:
            raise ValueError('Explicit local serving acknowledgement required')
        from app.p101_local_demo.api import create_app
        import uvicorn
        uvicorn.run(create_app(settings),host='127.0.0.1',port=8001,proxy_headers=False,
                    server_header=False,access_log=False)
        return 0
    except Exception:
        print('P101_LOCAL_READER_API_REFUSED')
        return 1


if __name__=='__main__':
    raise SystemExit(main())
