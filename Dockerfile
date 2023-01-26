FROM python

EXPOSE 8080
WORKDIR /tmp

COPY . . 

RUN pip install .

ENTRYPOINT ["phserver", "-a", "0.0.0.0"]
