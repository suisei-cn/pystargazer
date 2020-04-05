# PyStargazer
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

## License
This project is licensed under MIT License - see the [LICENSE](LICENSE) file for details.
