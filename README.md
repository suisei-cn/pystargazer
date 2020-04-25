# PyStargazer
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fsuisei-cn%2Fpystargazer.svg?type=shield)](https://app.fossa.io/projects/git%2Bgithub.com%2Fsuisei-cn%2Fpystargazer?ref=badge_shield)

> WIP: This project is undergoing a major refactoring, and its API is expected to be changed
> greatly in several days.

PyStargazer is a flexible vtuber tracker.
It's now capable of monitoring Youtube live status, new tweets, and bilibili dynamic.

It's originally written to track [@suisei_hosimati](https://twitter.com/suisei_hosimati)'s 
tweets and live broadcasts, but you can also use it to monitor other vtuber, and track
multiple vtubers if you want to.

The tracker will expose a set of restful manage endpoints and a websocket endpoint.
When a new tweet or live broadcast is detected, it will push the event to any connected
websocket client. Therefore, it's easy to integrate the tracker with chat services like Telegram and QQ.

## Usage
### Docker
Modify the [docker-compose.yml](docker-compose.yml) file, copy [Dockerfile](Dockerfile) and 
other required files to `stargazer` folder, put your tokens in `stargazer-data/tokens.json`, and
``` shell script
docker-compose up -d --build
```
Don't forget to add your chat service integration dockers into the docker-compose file.

Expose the tracker's HTTP port to public if you want to monitor youtube broadcasts.

### Linux
Copy `tokens_example.json` to `tokens.json`, and fill in your tokens, then

``` shell script
python -m pystargazer
```

Expose the tracker's HTTP port to public if you want to monitor youtube broadcasts.

## Installation
### Arch Linux
Use PKGBUILD to build the package and install.

``` shell script
git clone https://github.com/suisei-cn/archpkgs.git
cd archpkgs/pystargazer-git
makepkg
pacman -U pystargazer-git-rx.xxxxxxx-1-any.pkg.tar.zst
```

### setuptools
Clone this repo and use setup.py to build and install.

``` shell script
git clone https://github.com/suisei-cn/pystargazer.git
cd pystargazer
python setup.py build && python setup.py install
```

## License
This project is licensed under MIT License - see the [LICENSE](LICENSE) file for details.


[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fsuisei-cn%2Fpystargazer.svg?type=large)](https://app.fossa.io/projects/git%2Bgithub.com%2Fsuisei-cn%2Fpystargazer?ref=badge_large)