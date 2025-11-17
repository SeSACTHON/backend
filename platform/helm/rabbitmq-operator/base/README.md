# RabbitMQ Operator Base

RabbitMQ Cluster Operator(`github.com/rabbitmq/cluster-operator`)를
App-of-Apps 구조에서 재사용하기 위한 공통 `Application` 정의입니다.

- `application.yaml`: upstream `config/default` 매니페스트를 그대로 소싱하는
  Argo CD Application 정의
- `kustomization.yaml`: base Application을 단일 리소스로 노출

환경별(`dev`, `prod`) 오버레이는 `namePrefix`와 Patch를 통해
프로젝트/네임스페이스/주석 등을 주입합니다.
