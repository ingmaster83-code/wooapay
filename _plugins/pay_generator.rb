require 'json'

module Jekyll
  class PayPageGenerator < Generator
    safe true
    priority :normal

    SIGUNGU_CAP = 300  # 시군구 페이지당 서버사이드 렌더링 상한 (대형 시군구 대응)

    def generate(site)
      raw_dir = File.join(site.source, '_rawdata')
      shard_files = Dir.glob(File.join(raw_dir, 'pay_*.json'))
                        .reject { |f| File.basename(f) == 'pay_raw.json' }

      total_stores = 0
      total_sigungu = 0

      shard_files.each do |path|
        do_short = File.basename(path, '.json').sub('pay_', '')
        items = load_json(path)
        next if items.empty?

        by_sigungu = items.group_by { |i| i['sigungu'].to_s.strip }
        by_sigungu.delete('')

        site.pages << DoIndexPage.new(site, do_short, items.size, by_sigungu)
        total_sigungu += by_sigungu.size

        by_sigungu.each do |sigungu, list|
          site.pages << SigunguPage.new(site, do_short, sigungu, list)
          total_stores += list.size
        end
      end

      Jekyll.logger.info "PayGenerator:", "완료 (시도 #{shard_files.size}개 + 시군구 #{total_sigungu}개, 가맹점 #{total_stores}건은 지역페이지 목록+클라이언트 검색으로만 제공)"
    end

    private

    def load_json(path)
      return [] unless File.exist?(path)
      JSON.parse(File.read(path, encoding: 'utf-8'))
    rescue => e
      Jekyll.logger.warn "PayGenerator:", "#{path} 로드 실패: #{e.message}"
      []
    end
  end

  class DoIndexPage < Page
    def initialize(site, do_short, total_count, by_sigungu)
      @site = site
      @base = site.source
      @dir  = "region/#{do_short}"
      @name = 'index.html'

      sigungu_list = by_sigungu.map { |sg, list| { 'name' => sg, 'count' => list.size } }
                               .sort_by { |h| -h['count'] }

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'do.html')
      self.data['doShort']     = do_short
      self.data['totalCount']  = total_count
      self.data['sigunguList'] = sigungu_list
      self.data['layout']      = 'do'
      self.data['title']       = "#{do_short} 지역화폐 가맹점 #{total_count}곳"
      self.data['description'] = "#{do_short} 지역 지역화폐(지역사랑상품권) 가맹점 #{total_count}곳을 시군구별로 확인하세요."[0, 155]
    end
  end

  class SigunguPage < Page
    def initialize(site, do_short, sigungu, list)
      @site = site
      @base = site.source
      @dir  = "region/#{do_short}/#{sigungu}"
      @name = 'index.html'

      capped = list.first(PayPageGenerator::SIGUNGU_CAP)

      self.process(@name)
      self.read_yaml(File.join(@base, '_layouts'), 'sigungu.html')
      self.data['doShort']    = do_short
      self.data['sigungu']    = sigungu
      self.data['totalCount'] = list.size
      self.data['truncated']  = list.size > PayPageGenerator::SIGUNGU_CAP
      self.data['items']      = capped
      self.data['layout']     = 'sigungu'
      self.data['title']      = "#{do_short} #{sigungu} 지역화폐 가맹점 #{list.size}곳"
      self.data['description'] = "#{do_short} #{sigungu}에서 지역화폐로 결제 가능한 가맹점 #{list.size}곳의 업종·주소·연락처를 확인하세요."[0, 155]
    end
  end
end
