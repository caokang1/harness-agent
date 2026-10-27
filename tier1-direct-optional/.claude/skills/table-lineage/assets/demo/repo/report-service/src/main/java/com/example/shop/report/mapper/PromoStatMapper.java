package com.example.shop.report.mapper;

import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Update;

@Mapper
public interface PromoStatMapper {

    @Update("update old_promo_stat set cnt = cnt + 1 where day = #{day}")
    int increase(@Param("day") String day);
}
