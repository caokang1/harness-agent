package com.example.shop.report.mapper;

import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;

@Mapper
public interface StoreMapper {

    @Insert("replace into store (id, store_name) values (#{id}, #{name})")
    int upsert(@Param("id") Long id, @Param("name") String name);
}
