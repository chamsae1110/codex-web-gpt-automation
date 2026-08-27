# 공개 소개문 안내

이 문서는 예전 CodexPro/agbrowse 기반 소개문을 더 이상 배포하지 않도록
남겨 둔 호환 파일입니다.

현재 구조는 새 GPT 작업을 전부 Oracle로 실행합니다. 일반 GPT·종합모드·
웹 멀티 GPT와 명시적으로 요청한 Pro는 수동 등록 DevSpace 앱을 사용합니다.
신규 Pro의 `pro-devspace`는 exact root에서 파일 변경, 명령·테스트, 네트워크,
사용자 소유 Chrome CDP 검증과 반복 에이전트 코딩을 수행하는 전체 권한 경로입니다.
명시적 `pro-attachment`는 불변·외부 증거를 위한 별도 읽기 전용 경로이며 자동 fallback이
아닙니다. 저장된 `pro-devspace-readonly` 실행은 정확한 복구에서만 원래 권한을 유지합니다.
CodexPro와 agbrowse는 과거 실행 복구에만 남아 있으며 새 작업의
대체 경로로 사용하지 않습니다.

최신 설치 및 모드 설명은 [README](../README.md)와
[GLOBAL_CHATGPT_ROUTING.md](GLOBAL_CHATGPT_ROUTING.md)를 참고하세요.

동결된 자산의 정확한 목록과 경계는
[FROZEN_LEGACY.md](FROZEN_LEGACY.md)에 있습니다.
